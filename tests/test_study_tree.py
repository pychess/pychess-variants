from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from study.annotations import StudyAnnotations, StudyComment, StudyShape
from study.tree import (
    STUDY_NODE_ID_LENGTH,
    STUDY_TREE_ROOT_KEY,
    StudyGamebook,
    StudyTree,
    StudyTreeNode,
    StudyTurnColor,
    is_study_node_id,
    new_study_node_id,
)

ROOT_A = "RootNode01"
ROOT_B = "RootNode02"
CHILD_A = "ChildNode1"
DEEP_A = "DeepNode01"


def make_node(
    node_id: str,
    *,
    parent_id: str | None = None,
    order: int = 0,
    move: str = "e2e4",
    fen: str = "fen after move",
    turn_color: StudyTurnColor = "black",
    check: bool = False,
    force_variation: bool = False,
    annotations: StudyAnnotations | None = None,
    gamebook: StudyGamebook | None = None,
    eval_score: dict[str, int] | None = None,
    clocks: tuple[int | float, int | float] | None = None,
) -> StudyTreeNode:
    return StudyTreeNode(
        id=node_id,
        parent_id=parent_id,
        order=order,
        move=move,
        fen=fen,
        turn_color=turn_color,
        check=check,
        san="e4",
        san_san="e4",
        force_variation=force_variation,
        annotations=annotations or StudyAnnotations(),
        gamebook=gamebook or StudyGamebook(),
        eval_score=eval_score,
        clocks=clocks,
    )


class StudyTreeTestCase(unittest.TestCase):
    def test_children_and_mainline_follow_order_after_tree_changes(self) -> None:
        first = make_node(ROOT_A)
        other = make_node(ROOT_B, order=1)
        child = make_node(CHILD_A, parent_id=ROOT_A)
        tree = StudyTree({ROOT_B: other, CHILD_A: child, ROOT_A: first})
        self.assertEqual(tree.children_of(None), (first, other))
        self.assertEqual(tree.children_of(ROOT_A), (child,))
        self.assertEqual(tree.children_of(ROOT_B), ())
        self.assertEqual(tree.children_of("missing"), ())
        self.assertEqual(tree.preferred_mainline(), (first, child))

        promoted = replace(
            tree,
            nodes={ROOT_A: replace(first, order=1), ROOT_B: replace(other, order=0)},
        )
        self.assertEqual(promoted.preferred_mainline_path(), ROOT_B)
        forced = replace(promoted, nodes={ROOT_B: replace(other, order=0, force_variation=True)})
        self.assertEqual(forced.preferred_mainline(), ())
        stopped = replace(
            tree, nodes={ROOT_A: first, CHILD_A: replace(child, force_variation=True)}
        )
        self.assertEqual(stopped.preferred_mainline(), (first,))
        self.assertEqual(tree.preferred_mainline(), (first, child))

    def test_tree_nodes_are_detached_and_read_only(self) -> None:
        node = make_node(ROOT_A)
        supplied = {ROOT_A: node}
        tree = StudyTree(supplied)
        supplied.clear()
        self.assertEqual(tree.count(), 1)
        self.assertEqual(tree.children_of(None), (node,))
        with self.assertRaises(TypeError):
            tree.nodes[ROOT_B] = make_node(ROOT_B, order=1)  # type: ignore[index]

    def test_node_ids_are_compact_collision_resistant_path_segments(self) -> None:
        ids = {new_study_node_id() for _ in range(200)}
        self.assertEqual(len(ids), 200)
        self.assertTrue(all(len(node_id) == STUDY_NODE_ID_LENGTH for node_id in ids))
        self.assertTrue(all(is_study_node_id(node_id) for node_id in ids))

    def test_flat_document_round_trip_preserves_order_and_force_variation(self) -> None:
        tree = StudyTree(
            {
                ROOT_A: make_node(ROOT_A, move="e2e4"),
                ROOT_B: make_node(ROOT_B, order=1, move="d2d4", force_variation=True),
                CHILD_A: make_node(CHILD_A, parent_id=ROOT_A, move="e7e5", turn_color="white"),
            }
        )

        doc = tree.to_document()
        self.assertEqual(doc[STUDY_TREE_ROOT_KEY], {})
        self.assertEqual(doc[ROOT_A]["p"], STUDY_TREE_ROOT_KEY)  # type: ignore[index]
        self.assertNotIn("children", doc[ROOT_A])  # type: ignore[operator]
        self.assertEqual(doc[ROOT_B]["o"], 1)  # type: ignore[index]
        self.assertTrue(doc[ROOT_B]["v"])  # type: ignore[index]

        restored = StudyTree.from_document(doc)
        self.assertEqual(restored, tree)
        self.assertEqual([node.id for node in restored.children_of(None)], [ROOT_A, ROOT_B])
        self.assertEqual(restored.children_of(ROOT_A)[0].id, CHILD_A)

    def test_root_and_node_annotations_round_trip_in_document_and_payload(self) -> None:
        root_annotations = StudyAnnotations(
            shapes=(StudyShape("e4", "e5", "red"),),
            comments=(StudyComment("Comment001", "owner", "Root note"),),
            nags=(1, 3),
        )
        node_annotations = StudyAnnotations(
            shapes=(StudyShape("d4", brush="blue"),),
            comments=(StudyComment("Comment002", "owner", "Node note"),),
            nags=(2,),
        )
        tree = StudyTree(
            {
                ROOT_A: make_node(
                    ROOT_A,
                    annotations=node_annotations,
                    eval_score={"cp": 42},
                    clocks=(298000, 300000),
                    gamebook=StudyGamebook(hint="Node hint", deviation="Try another move"),
                )
            },
            root_annotations=root_annotations,
            root_gamebook=StudyGamebook(hint="Root hint"),
            root_eval_score={"mate": -2},
            root_clocks=(300000, 300000),
        )

        doc = tree.to_document()
        self.assertEqual(doc[STUDY_TREE_ROOT_KEY]["a"]["n"], [1, 3])  # type: ignore[index]
        self.assertEqual(doc[STUDY_TREE_ROOT_KEY]["k"], [300000, 300000])  # type: ignore[index]
        self.assertEqual(doc[STUDY_TREE_ROOT_KEY]["g"], {"h": "Root hint"})
        self.assertEqual(doc[STUDY_TREE_ROOT_KEY]["e"], {"mate": -2})  # type: ignore[index]
        self.assertIn("a", doc[ROOT_A])  # type: ignore[operator]
        self.assertEqual(
            doc[ROOT_A]["g"],  # type: ignore[index]
            {"h": "Node hint", "d": "Try another move"},
        )
        self.assertEqual(doc[ROOT_A]["e"], {"cp": 42})  # type: ignore[index]
        self.assertEqual(doc[ROOT_A]["k"], [298000, 300000])  # type: ignore[index]
        self.assertEqual(StudyTree.from_document(doc), tree)

        payload = tree.to_payload()
        self.assertEqual(payload["rootAnnotations"]["nags"], [1, 3])  # type: ignore[index]
        self.assertEqual(payload["rootClocks"], [300000, 300000])
        self.assertEqual(payload["rootGamebook"], {"hint": "Root hint"})
        self.assertEqual(payload["rootEval"], {"mate": -2})
        self.assertEqual(
            payload["nodes"][0]["gamebook"],  # type: ignore[index]
            {"hint": "Node hint", "deviation": "Try another move"},
        )
        self.assertEqual(payload["nodes"][0]["eval"], {"cp": 42})  # type: ignore[index]
        self.assertEqual(StudyTree.from_payload(payload), tree)

    def test_payload_rejects_node_limit_before_parsing_nodes(self) -> None:
        payload = {"nodes": [{}, {}]}
        with (
            patch("study.tree.STUDY_MAX_NODES_PER_CHAPTER", 1),
            self.assertRaisesRegex(ValueError, "maximum is 1"),
        ):
            StudyTree.from_payload(payload)

    def test_gamebook_text_uses_comment_sanitization_and_empty_values_remove_fields(self) -> None:
        gamebook = StudyGamebook(hint="  hello\x00 world  ", deviation="   ")
        self.assertEqual(gamebook.hint, "hello world")
        self.assertIsNone(gamebook.deviation)
        self.assertEqual(gamebook.to_payload(), {"hint": "hello world"})

        with self.assertRaisesRegex(ValueError, "too long"):
            StudyGamebook(hint="x" * 4_001)

    def test_payload_round_trip_and_stable_path_resolution(self) -> None:
        tree = StudyTree(
            {
                ROOT_A: make_node(ROOT_A),
                CHILD_A: make_node(CHILD_A, parent_id=ROOT_A, move="e7e5", turn_color="white"),
                DEEP_A: make_node(DEEP_A, parent_id=CHILD_A, move="g1f3"),
            }
        )

        payload = tree.to_payload()
        restored = StudyTree.from_payload(payload)
        self.assertEqual(restored, tree)
        path = f"{ROOT_A}.{CHILD_A}.{DEEP_A}"
        self.assertEqual(restored.path_for_node(DEEP_A), path)
        self.assertEqual(restored.node_at_path(path), restored.nodes[DEEP_A])
        self.assertIsNone(restored.node_at_path(f"{ROOT_B}.{CHILD_A}"))

    def test_rejects_malformed_root_eval(self) -> None:
        payload = StudyTree().to_payload()
        payload["rootEval"] = {"cp": "bad"}
        with self.assertRaises(TypeError):
            StudyTree.from_payload(payload)

    def test_rejects_malformed_node_eval(self) -> None:
        payload = make_node(ROOT_A).to_payload()
        payload["eval"] = {"cp": "bad"}
        with self.assertRaises(TypeError):
            StudyTreeNode.from_payload(payload)

    def test_rejects_duplicate_sibling_order(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate order"):
            StudyTree(
                {
                    ROOT_A: make_node(ROOT_A),
                    ROOT_B: make_node(ROOT_B, move="d2d4"),
                }
            )

    def test_rejects_parent_cycles(self) -> None:
        with self.assertRaisesRegex(ValueError, "parent cycle"):
            StudyTree(
                {
                    ROOT_A: make_node(ROOT_A, parent_id=ROOT_B),
                    ROOT_B: make_node(ROOT_B, parent_id=ROOT_A, move="d2d4"),
                }
            )

    def test_long_mainline_stays_flat_and_non_recursive(self) -> None:
        nodes: dict[str, StudyTreeNode] = {}
        parent_id: str | None = None
        for idx in range(1_200):
            node_id = f"N{idx:09d}"
            nodes[node_id] = make_node(node_id, parent_id=parent_id, move=f"m{idx}")
            parent_id = node_id

        tree = StudyTree(nodes)
        doc = tree.to_document()
        restored = StudyTree.from_document(doc)
        self.assertEqual(restored.count(), 1_200)
        self.assertEqual(len(doc), 1_201)
        self.assertEqual(restored.preferred_mainline(), tuple(nodes.values()))


if __name__ == "__main__":
    unittest.main()
