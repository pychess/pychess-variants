import { describe, expect, test } from '@jest/globals';

import { isParticipantStatus } from '../client/tournamentUserStatus';

describe('scroll-to-player icon visibility', () => {
    test.each(['joined', 'paused', 'withdrawn'])('shows the icon for a %s player', status => {
        expect(isParticipantStatus(status)).toBe(true);
    });

    test.each(['spectator', 'pending', 'denied', '', 'undefined'])(
        'hides the icon for a non-participant status "%s"',
        status => {
            expect(isParticipantStatus(status)).toBe(false);
        },
    );
});
