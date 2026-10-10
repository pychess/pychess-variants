/** Whether a forum redirect stays on the current document and only changes its fragment. */
export function isSameDocumentForumRedirect(redirectHref: string, currentHref = window.location.href): boolean {
    const current = new URL(currentHref);
    const redirect = new URL(redirectHref, current);
    return (
        redirect.origin === current.origin &&
        redirect.pathname === current.pathname &&
        redirect.search === current.search
    );
}
