import { isSameDocumentForumRedirect } from '../client/forumNavigation';

describe('forum reply redirects', () => {
    test('recognizes a new post fragment on the already-open topic page', () => {
        expect(
            isSameDocumentForumRedirect(
                '/forum/general-chess-discussion/topic?page=1#new-post',
                'https://pychess.org/forum/general-chess-discussion/topic?page=1#old-post',
            ),
        ).toBe(true);
    });

    test('keeps normal navigation when the reply moves to another topic page', () => {
        expect(
            isSameDocumentForumRedirect(
                '/forum/general-chess-discussion/topic?page=2#new-post',
                'https://pychess.org/forum/general-chess-discussion/topic?page=1#old-post',
            ),
        ).toBe(false);
    });

    test('keeps normal navigation when page=1 is newly added to the URL', () => {
        expect(
            isSameDocumentForumRedirect(
                '/forum/general-chess-discussion/topic?page=1#new-post',
                'https://pychess.org/forum/general-chess-discussion/topic',
            ),
        ).toBe(false);
    });
});
