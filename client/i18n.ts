import { h, VNode } from 'snabbdom';

import gettext from 'gettext.js';

import { StringSettings } from './settings';
import { radioList } from './view';

export const i18n = gettext();
export function _(msgid: string, ...vars: any): string {
    return i18n.gettext(msgid, vars);
}
// Marks a msgid for extraction without translating it, for tables built before translations load.
// Translate it with _() where it is shown.
export function N_(msgid: string): string {
    return msgid;
}
export function ngettext(msgid: string, plural: string, n: number) {
    return i18n.ngettext(msgid, plural, n, n);
}
export function pgettext(msgctxt: string, msgid: string, ...vars: any) {
    return i18n.pgettext(msgctxt, msgid, vars);
}

export const LANGUAGES = {
    en: 'English',
    de: 'Deutsch',
    es: 'Español',
    fr: 'Français',
    gl_ES: 'Galego',
    hu: 'Magyar',
    it: 'Italiano',
    ja: '日本語',
    ko: '한국어',
    nl: 'Nederlands',
    pl: 'Polski',
    pt: 'Português',
    ru: 'Русский',
    th: 'ไทย',
    tr: 'Türkçe',
    vi: 'Tiếng Việt',
    zh_CN: '简体中文',
    zh_TW: '繁體中文',
};

const LANGUAGETEXT: { [key: string]: string } = {
    en: 'Language',
    de: 'Sprache',
    es: 'Idioma',
    fr: 'Langue',
    gl_ES: 'Lingua',
    hu: 'Nyelv',
    it: 'Lingua',
    ja: '言語',
    ko: '언어',
    nl: 'Taal',
    pl: 'Język ',
    pt: 'Lingua',
    ru: 'Язык',
    th: 'ภาษา',
    tr: 'Dil',
    vi: 'Ngôn ngữ',
    zh_CN: '语言',
    zh_TW: '語言',
};

const preferredLang = window.navigator.language.slice(0, 2);
export const translatedLanguage = LANGUAGETEXT[preferredLang] ?? 'Language';
export const translatedGameCategory = _('Game Category');

export const GAME_CATEGORY_LABELS: { [key: string]: string } = {
    all: _('All'),
    chess: _('Chess Variants'),
    makruk: _('Makruk Variants'),
    shogi: _('Shogi Variants'),
    xiangqi: _('Xiangqi Variants'),
    fairy: _('Fairy Piece Variants'),
    army: _('New Army Variants'),
    other: _('Other'),
};

export function gameCategoryLabel(key: string): string {
    return GAME_CATEGORY_LABELS[key] ?? key;
}

// Do not use
// These lists are only here to mark these texts translatable
// Use the regular translate functions if these words are determined at runtime
export const translatedColorNames = [_('White'), _('Black'), _('Red'), _('Blue'), _('Gold'), _('Pink'), _('Green')];

export const translatedPieceNames = [
    _('pawn'),
    _('knight'),
    _('bishop'),
    _('rook'),
    _('queen'),
    _('king'),
    _('horse'),
    _('elephant'),
    _('chariot'),
    _('cannon'),
    _('advisor'),
];

export const translatedVariantDisplayNames = [
    _('chess'),
    _('bughouse'),
    _('crazyhouse'),
    _('placement'),
    _('atomic'),
    _('king of the hill'),
    _('three-check'),
    _('antichess'),
    _('racing kings'),
    _('horde'),
    _('duck'),
    _('alice'),
    _('fog of war'),

    _('makruk'),
    _('makbug'),
    _('makpong'),
    _('ouk chaktrang'),
    _('sittuyin'),
    _('asean'),

    _('shogi'),
    _('sho shogi'),
    _('minishogi'),
    _('kyoto shogi'),
    _('dobutsu'),
    _('gorogoro'),
    _('gorogoro+'),
    _('tori shogi', _('cannon shogi')),

    _('xiangqi'),
    _('supply chess'),
    _('manchu'),
    _('janggi'),
    _('minixiangqi'),

    _('shatranj'),
    _('capablanca'),
    _('caparandom'),
    _('capahouse'),
    _('dragon chess'),
    _('s-chess'),
    _('s-house'),
    _('grand'),
    _('grandhouse'),
    _('shako'),
    _('shogun'),
    _('hoppel-poppel'),
    _('mansindam'),

    _('orda'),
    _('khans'),
    _('synochess'),
    _('shinobi'),
    _('shinobi+'),
    _('empire'),
    _('orda mirror'),
    _('chak'),
    _('chennis'),
];

export const translatedCustomStartPositions = [
    _('PawnsPushed'),
    _('PawnsPassed'),
    _('UpsideDown'),
    _('Theban'),
    _('No castle'),

    _('Lance HC'),
    _('Bishop HC'),
    _('Rook HC'),
    _('Rook+Lance HC'),
    _('2-Piece HC'),
    _('4-Piece HC'),
    _('6-Piece HC'),
    _('8-Piece HC'),
    _('9-Piece HC'),
    _('10-Piece HC'),

    _('Gorogoro Plus N+L'),
    _('Original (No N+L)'),

    _('Left Quail HC'),
    _('Falcon HC'),
    _('Falcon + Left Quail HC'),
    _('Falcon + Both Quails HC'),

    _('Bird'),
    _('Carrera'),
    _('Gothic'),
    _('Embassy'),
    _('Conservative'),
];

export const translatedTooltips = [
    _('Martial arts Xiangqi.'),
    _('Infection game.'),
    _("Chess, unmodified, as it's played by FIDE standards."),
    _('Take captured pieces and drop them back on to the board as your own.'),
    _('Choose where your pieces start.'),
    _('Pieces explode upon capture.'),
    _('Bring your King to the center to win the game.'),
    _('Check your opponent 3 times to win the game.'),
    _('Lose all your pieces to win.'),
    _('Race your King to the eighth rank to win.'),
    _('Destroy the horde to win!'),
    _('The duck must be moved to a new square after every turn.'),
    _('Through the Looking-Glass'),
    _('Players can only see the squares to which their pieces can legally move to.'),
    _(
        'Thai Chess. A game closely resembling the original Chaturanga. Similar to Chess but with a different queen and bishop.',
    ),
    _('Makruk variant where kings cannot move to escape out of check.'),
    _('Cambodian Chess. Makruk with a few additional opening abilities.'),
    _('Burmese Chess. Similar to Makruk, but pieces are placed at the start of the match.'),
    _('Makruk using the board/pieces from International Chess as well as pawn promotion rules.'),
    _('Japanese Chess, the standard 9x9 version played today with drops and promotions.'),
    _('Historical 9x9 Shogi with a drunken elephant piece and no drops.'),
    _('Shogi with Chinese and Korean cannons'),
    _('5x5 Shogi for more compact and faster games. There are no knights or lances.'),
    _('A wild Shogi variant on a 5x5 board where pieces flip into a different piece after each move.'),
    _('3x4 game with cute animals, designed to teach children how to play Shogi.'),
    _('5x6 Shogi designed to introduce tactics with the generals.'),
    _('A confrontational 7x7 variant with unique pieces each named after different birds.'),
    _('Chinese Chess, one of the oldest and most played board games in the world.'),
    _('Xiangqi variant where one side has a chariot that can also move as a cannon or horse.'),
    _('Korean Chess, similar to Xiangqi but plays much differently. Tournament rules are used.'),
    _('Compact version of Xiangqi played on a 7x7 board without a river.'),
    _('Ancient Arabian and Persian form of Chess.'),
    _('The dragon can be dropped to the base rank.'),
    _('Play with the hybrid pieces, archbishop (B+N) and chancellor (R+N), on a 10x8 board.'),
    _('Capablanca with Crazyhouse drop rules.'),
    _('Hybrid pieces, the hawk (B+N) and elephant (R+N), can enter the board after moving a back rank piece.'),
    _('S-Chess with Crazyhouse drop rules.'),
    _('Play with the hybrid pieces, archbishop (B+N) and chancellor (R+N), on a grand 10x10 board.'),
    _('Grand Chess with Crazyhouse drop rules.'),
    _('Introduces the cannon and elephant from Xiangqi into a 10x10 chess board.'),
    _('Pieces promote and can be dropped, similar to Shogi.'),
    _('Knights capture as bishops; bishops  capture as knights.'),
    _('Asymmetric variant where one army has pieces that move like knights but capture differently.'),
    _('Asymmetric East vs. West variant which pits the western Chess army against a Xiangqi and Janggi-styled army.'),
    _('Asymmetric variant which pits the western Chess army against a drop-based, Shogi-styled army.'),
    _('Asymmetric variant where one army has pieces that move like queens but capture as usual.'),
    _('Orda Chess variant. The scout and khatun replaces the pawn and yurt.'),
    _('Orda Chess variant with two Horde armies. The Falcon replaces the Yurt.'),
    _('Mayan chess. Inspired by cultural elements of Mesoamerica.'),
    _('Pieces alternate between two forms with each move.'),
    _('Asymmetric Spartans vs. Persians variant.'),
    _("A variant that combines the Shogi's drop rule with strong pieces."),
    _('Like Capablanca Chess but with Grand starting setup.'),
    _('Embassy with Crazyhouse drop rules.'),
    _('Like Capablanca Chess but with a different starting setup.'),
    _('Gothic with Crazyhouse drop rules.'),
];

class LanguageSettings extends StringSettings {
    constructor() {
        super('lang', 'en');
    }

    update(): void {}

    view(): VNode {
        const langList = radioList(this, 'lang', LANGUAGES, (evt, key) => {
            this.value = key;
            (evt.target as HTMLInputElement).form!.submit();
        });
        return h('div#settings-lang', [
            h('form.radio-list', { props: { method: 'post', action: '/translation/select' } }, langList),
        ]);
    }
}

export const languageSettings = new LanguageSettings();
