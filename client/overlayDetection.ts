export function startOverlayObservation(board: Element, onCandidate: (svg: string) => void): () => void {
    let reported = false;
    const isCandidate = (node: Node): boolean => {
        if (!(node instanceof SVGSVGElement) || node.parentElement !== document.body) return false;
        if (node.style.position !== 'absolute' || node.style.pointerEvents !== 'none') return false;
        if (node.querySelectorAll('polygon[points]').length === 0) return false;

        const boardRect = board.getBoundingClientRect();
        const overlayRect = node.getBoundingClientRect();
        if (boardRect.width <= 0 || boardRect.height <= 0) return false;
        const width = Math.max(0, Math.min(boardRect.right, overlayRect.right) - Math.max(boardRect.left, overlayRect.left));
        const height = Math.max(0, Math.min(boardRect.bottom, overlayRect.bottom) - Math.max(boardRect.top, overlayRect.top));
        return (width * height) / (boardRect.width * boardRect.height) >= 0.75;
    };
    const inspect = (node: Node): void => {
        if (!reported && isCandidate(node)) {
            reported = true;
            observer.disconnect();
            // Capture the exact DOM snapshot while the candidate is still attached.
            onCandidate(new XMLSerializer().serializeToString(node));
        }
    };
    const observer = new MutationObserver(records => {
        for (const record of records) {
            record.addedNodes.forEach(node => {
                inspect(node);
                // The SVG may be inserted before the arrow polygons.
                if (node instanceof Element) {
                    const svg = node.closest('svg');
                    if (svg) inspect(svg);
                }
            });
        }
    });
    observer.observe(document.body, {
        childList: true,
        subtree: true,
    });
    document.body.querySelectorAll(':scope > svg').forEach(inspect);
    return () => observer.disconnect();
}
