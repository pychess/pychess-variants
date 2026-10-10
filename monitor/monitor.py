import logging
import os
from datetime import datetime
from typing import ClassVar
from urllib.parse import urlparse

import aiohttp
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    Rule,
    Sparkline,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)

from monitor.metrics_client import fetch_metrics, metrics_url, monitor_token, monitor_view

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MIN_PRODUCTION_INTERVAL_SECONDS = 60.0
DEFAULT_UPDATE_INTERVAL_SECONDS = 600.0


class MemoryMonitorApp(App):
    """Textual TUI app to monitor aiohttp server memory usage and object usage."""

    CSS = """
    Screen {
        layout: vertical;
    }

    .container {
        height: auto;
        width: auto;
    }

    Static {
        margin: 1;
    }

    Switch {
        height: auto;
        width: auto;
    }

    DataTable {
        height: 1fr;
        background: $panel;
        border: $secondary;
    }

    TabbedContent {
        height: 1fr;
        min-height: 10;
        background: $panel;
        border: $secondary;
    }

    Label {
        margin: 0 1;
        width: 100%;
    }

    .label {
        width: auto;
    }

    Sparkline {
        margin: 1;
        width: 100%;
    }

    Vertical {
        align: center middle;
    }

    #left_panel {
        width: 25%;
        background: $panel;
        border: $secondary;
        content-align: center middle;
    }

    #right_panel {
        width: 75%;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("d", "snapshot", "Full snapshot"),
        ("i", "inspect", "Task locations"),
    ]

    monitoring = reactive(True)  # switch on/off

    categories: reactive[list[str]] = reactive([])

    column_configs: reactive[dict[str, list[tuple[str, str]]]] = reactive({})

    category_counts: reactive[dict[str, int]] = reactive({})
    category_memories: reactive[dict[str, float]] = reactive({})
    category_histories: reactive[dict[str, list[int]]] = reactive({})

    top_allocations: reactive[list[tuple[str, int, int, str]]] = reactive([])
    object_details: reactive[dict[str, list[dict[str, object]]]] = reactive({})

    sort_columns: reactive[dict[str, str | None]] = reactive({})
    sort_ascendings: reactive[dict[str, bool]] = reactive({})

    def __init__(self):
        super().__init__()
        configured_interval = float(
            os.getenv("PYCHESS_MONITOR_INTERVAL_SECONDS", DEFAULT_UPDATE_INTERVAL_SECONDS)
        )
        hostname = urlparse(metrics_url()).hostname
        is_local = hostname in {"localhost", "127.0.0.1", "::1"}
        self.update_interval = (
            configured_interval
            if is_local
            else max(MIN_PRODUCTION_INTERVAL_SECONDS, configured_interval)
        )
        self.max_history = 100
        self.ui_setup_done = False
        self._fetching = False
        self.measured_sizes: set[str] = set()

    @staticmethod
    def build_column_config(items: list[dict[str, object]]) -> list[tuple[str, str]]:
        keys = sorted({key for item in items for key in item})
        return [(key.replace("_", " ").title(), key) for key in keys]

    def sync_category_columns(self, category: str) -> None:
        try:
            table = self.query_one(f"#{category}_table", DataTable)
        except NoMatches:
            return

        columns = self.column_configs.get(category, [])
        table.clear(columns=True)
        if not columns:
            table.add_column("No Data", key="no_data")
            return

        for label, _ in columns:
            table.add_column(label, key=label)

    def compose(self) -> ComposeResult:
        """Compose the TUI layout."""
        yield Header()
        with Horizontal():
            with Vertical(id="left_panel"):
                yield Horizontal(
                    Static("Monitoring:", classes="label"),
                    Switch(value=True, id="monitoring"),
                    classes="container",
                )
                yield Rule()
            with Vertical(id="right_panel"):
                yield Label(
                    "Summary polling; D: full snapshot, I: task locations", id="metrics_status"
                )
                yield DataTable(id="alloc_table")
                yield TabbedContent(id="details_tabs")
        yield Footer()

    def watch_category_counts(self, value: dict) -> None:
        for cat, count in value.items():
            try:
                self.query_one(f"#{cat}_count_label", Label).update(f"{cat.capitalize()}: {count}")
            except NoMatches:
                pass

    def watch_category_memories(self, value: dict) -> None:
        for cat, mem in value.items():
            try:
                label = (
                    f"{cat.capitalize()} Mem: [b]{mem:.2f} KB[/b]"
                    if cat in self.measured_sizes
                    else f"{cat.capitalize()} Mem: not measured"
                )
                self.query_one(f"#{cat}_mem_label", Label).update(label)
            except NoMatches:
                pass

    def watch_category_histories(self, value: dict) -> None:
        for cat, hist in value.items():
            try:
                self.query_one(f"#{cat}_sparkline", Sparkline).data = hist
            except NoMatches:
                pass

    def watch_top_allocations(self, value: list) -> None:
        """Update allocation table when top_allocations changes."""
        alloc_table = self.query_one("#alloc_table", DataTable)
        alloc_table.clear()
        for alloc_type, count, size_bytes, size_human in value:
            alloc_table.add_row(alloc_type, str(count), str(size_bytes), size_human)

    def watch_object_details(self, value: dict) -> None:
        """Update all category tables when object_details changes."""
        for category in self.categories:
            self.update_category_table(category)

    def watch_sort_columns(self, value: dict) -> None:
        """Update tables when sort_columns changes."""
        for category, sort_column in value.items():
            if sort_column is not None:
                self.update_category_table(category)

    def watch_sort_ascendings(self, value: dict) -> None:
        """Update tables when sort_ascendings changes."""
        for category in value:
            if self.sort_columns[category] is not None:
                self.update_category_table(category)

    async def on_mount(self) -> None:
        """Set up the app on startup."""
        self.query_one("#left_panel").border_title = "App State"
        self.query_one("#alloc_table").border_title = "Alloc Table"
        self.query_one("#details_tabs").border_title = "Object Details"

        # Configure the allocation table
        alloc_table = self.query_one("#alloc_table", DataTable)
        alloc_table.add_columns("Type", "Count", "Size (bytes)", "Size (human)")
        alloc_table.zebra_stripes = True

        # Fetch once immediately, then continue at a production-safe interval.
        await self.update_metrics()
        if self.ui_setup_done:
            self.query_one("#details_tabs", TabbedContent).active = "process_memory_tab"
        self.set_interval(self.update_interval, self.update_metrics)

    async def setup_ui(self) -> None:
        if self.ui_setup_done:
            return
        left_panel = self.query_one("#left_panel")
        details_tabs = self.query_one("#details_tabs", TabbedContent)

        # First, create and mount all TabPane widgets
        for cat in self.categories:
            pane = TabPane(cat.capitalize(), id=f"{cat}_tab")
            await details_tabs.add_pane(pane)

        # Then, mount labels, sparklines, and tables
        for cat in self.categories:
            count_label = Label(id=f"{cat}_count_label")
            mem_label = Label(id=f"{cat}_mem_label")
            sparkline = Sparkline([], id=f"{cat}_sparkline")
            await left_panel.mount(count_label, mem_label, sparkline)

            table = DataTable(id=f"{cat}_table")
            await details_tabs.query_one(f"#{cat}_tab", TabPane).mount(table)

            self.sync_category_columns(cat)
            table.zebra_stripes = True
            table.cursor_type = "row"
            table.show_header = True
            table.show_cursor = True
            table.fixed_rows = 0

        self.ui_setup_done = True

    async def action_snapshot(self) -> None:
        await self.update_metrics(summary_only=False)

    async def action_inspect(self) -> None:
        await self.update_metrics(summary_only=False, inspect_tasks=True)

    async def update_metrics(
        self, *, summary_only: bool = True, inspect_tasks: bool = False
    ) -> None:
        """Fetch server metrics and update reactive variables."""
        if (summary_only and not self.monitoring) or self._fetching:
            return
        self._fetching = True

        async with aiohttp.ClientSession() as session:
            try:
                data = await fetch_metrics(
                    session,
                    url=metrics_url(),
                    token=monitor_token(),
                    inspect_tasks=inspect_tasks,
                    summary_only=summary_only,
                )
                if data:
                    data = monitor_view(data)
                    self.measured_sizes = set(data.get("object_sizes", {}))
                    mode = (
                        "Summary"
                        if data.get("mode") == "summary"
                        else "Full snapshot (cached up to 60s)"
                    )
                    self.query_one("#metrics_status", Label).update(
                        f"{mode}; sampled at {data.get('timestamp', '?')}"
                    )
                    logger.debug(
                        "Received metric categories: %s",
                        list(data.get("object_details", {})),
                    )

                    if not self.categories:
                        self.categories = list(data.get("object_details", {}).keys())
                        object_details = data.get("object_details", {})
                        self.column_configs = {}
                        for cat in self.categories:
                            items = object_details.get(cat, [])
                            self.column_configs[cat] = self.build_column_config(items)
                        self.sort_columns = {cat: None for cat in self.categories}
                        self.sort_ascendings = {cat: True for cat in self.categories}
                        self.category_histories = {cat: [] for cat in self.categories}
                        await self.setup_ui()
                        # Initialize counts and memories after UI setup
                        self.category_counts = {
                            cat: data.get("object_counts", {}).get(cat, 0)
                            for cat in self.categories
                        }
                        self.category_memories = {
                            cat: data.get("object_sizes", {}).get(cat, 0.0)
                            for cat in self.categories
                        }

                    else:
                        object_details = data.get("object_details", {})
                        new_column_configs = dict(self.column_configs)
                        columns_changed = False
                        changed_categories: list[str] = []
                        for cat in self.categories:
                            old_config = new_column_configs.get(cat, [])
                            items = object_details.get(cat, [])
                            keys = {key for _, key in old_config}
                            keys.update(key for item in items for key in item)
                            new_config = [
                                (key.replace("_", " ").title(), key) for key in sorted(keys)
                            ]
                            if new_config == old_config:
                                continue
                            new_column_configs[cat] = new_config
                            columns_changed = True
                            changed_categories.append(cat)

                        if columns_changed:
                            self.column_configs = new_column_configs
                            for cat in changed_categories:
                                self.sync_category_columns(cat)

                        self.category_counts = {
                            cat: data.get("object_counts", {}).get(cat, 0)
                            for cat in self.categories
                        }
                        self.category_memories = {
                            cat: data.get("object_sizes", {}).get(cat, 0.0)
                            for cat in self.categories
                        }

                    self.watch_category_memories(self.category_memories)
                    histories = self.category_histories.copy()
                    for cat in self.categories:
                        histories[cat] = histories[cat] + [self.category_counts[cat]]
                        histories[cat] = histories[cat][-self.max_history :]
                    self.category_histories = histories

                    self.top_allocations = [
                        (
                            alloc["type"],
                            alloc["count"],
                            alloc["size_bytes"],
                            alloc["size_human"],
                        )
                        for alloc in data.get("top_allocations", [])
                    ]
                    self.object_details = data.get(
                        "object_details",
                        {cat: [] for cat in self.categories},
                    )

            except (aiohttp.ClientError, TypeError, ValueError) as e:
                logger.error(f"Failed to fetch metrics: {e}")
                if self.categories:
                    self.category_counts = {cat: -1 for cat in self.categories}
            finally:
                self._fetching = False

    def update_category_table(self, category: str) -> None:
        """Update the details table for a specific category."""
        try:
            table = self.query_one(f"#{category}_table", DataTable)
        except NoMatches:
            return
        table.clear()  # Clear existing rows

        columns = self.column_configs.get(category, [])
        base_labels = {lbl: lbl for lbl, _ in columns}

        sort_column = self.sort_columns.get(category)
        sort_ascending = self.sort_ascendings.get(category, True)

        # Update column labels with sort indicators
        for col in table.columns.values():
            base_label_str = col.label.plain.strip(" ↑↓")
            base_label = base_labels.get(base_label_str, base_label_str)
            label = base_label
            if base_label == sort_column:
                label += " ↑" if sort_ascending else " ↓"
            col.label = Text(label)

        # Pre-sort data
        items = self.object_details.get(category, [])

        if sort_column and columns:
            data_key = next((dk for lbl, dk in columns if lbl == sort_column), None)
            if data_key:

                def sort_key(item):
                    value = item.get(data_key)
                    if isinstance(value, bool):
                        return (0, 1 if value else 0)
                    if isinstance(value, (int, float)):
                        return (1, value)
                    if isinstance(value, list):
                        return (2, ", ".join(map(str, value)))
                    if isinstance(value, str):
                        if data_key in {
                            "date",
                            "timestamp",
                            "last_seen",
                            "expire_at",
                        } or data_key.endswith("_at"):
                            try:
                                return (3, datetime.fromisoformat(value))
                            except Exception:
                                return (3, datetime.min)
                        return (4, value.casefold())
                    if value is None:
                        return (5, "")
                    return (6, str(value))

                try:
                    items = sorted(items, key=sort_key, reverse=not sort_ascending)
                except Exception as e:
                    self.notify(f"Sort failed: {e}", title="Error", severity="error", timeout=3)

        # Format values and add rows
        def format_date(value):
            try:
                return datetime.fromisoformat(value).strftime("%m/%d/%Y %H:%M") if value else "-"
            except (ValueError, TypeError):
                return "-"

        for item in items:
            row = []
            for _, key in columns or [("No Data", "no_data")]:
                value = item.get(key, "-")
                if key == "online":
                    formatted = "🟢" if value else "⚪"
                elif any(sub in key for sub in ["date", "time", "seen", "expire_at"]):
                    formatted = format_date(value)
                elif isinstance(value, list):
                    formatted = ", ".join(map(str, value))
                else:
                    formatted = str(value)
                row.append(formatted)
            table.add_row(*row)

        table.refresh()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "monitoring":
            self.monitoring = event.switch.value

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        table_id = event.data_table.id
        if table_id is not None and table_id.endswith("_table"):
            category = table_id[:-6]  # remove '_table'
            if category in self.sort_columns:
                column_key = event.column_key.value or ""
                new_sort_columns = dict(self.sort_columns)
                new_sort_ascendings = dict(self.sort_ascendings)
                if new_sort_columns[category] == column_key:
                    new_sort_ascendings[category] = not new_sort_ascendings[category]
                else:
                    new_sort_columns[category] = column_key
                    new_sort_ascendings[category] = True
                self.sort_columns = new_sort_columns
                self.sort_ascendings = new_sort_ascendings


if __name__ == "__main__":
    app = MemoryMonitorApp()
    app.run()
