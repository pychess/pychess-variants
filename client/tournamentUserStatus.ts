const PARTICIPANT_STATUSES = ['joined', 'paused', 'withdrawn'];

export function isParticipantStatus(ustatus: string): boolean {
    return PARTICIPANT_STATUSES.includes(ustatus);
}
