import { jest } from '@jest/globals';
import { h, type VNode } from 'snabbdom';

import { chatView } from '../client/chat';
import { patch } from '../client/document';

let chat: VNode;
let input: HTMLInputElement;
let board: HTMLElement;
const ctrl = { anon: false, doSend: jest.fn(), gameId: 'testgame' };

beforeEach(() => {
    document.body.innerHTML = '<div id="roundchat"></div><cg-board></cg-board>';
    chat = patch(document.getElementById('roundchat')!, chatView(ctrl, 'roundchat'));
    input = document.getElementById('chat-entry') as HTMLInputElement;
    board = document.querySelector('cg-board')!;
    input.value = 'unfinished message';
    input.focus();
});

afterEach(() => {
    patch(chat, h('div#roundchat'));
    document.body.innerHTML = '';
});

test.each(['touchstart', 'mousedown'])('blurs chat before the board handles %s, preserving the draft', eventType => {
    let focusedWhileHandling: Element | null | undefined;
    board.addEventListener(eventType, event => {
        event.preventDefault();
        event.stopPropagation();
        focusedWhileHandling = document.activeElement;
    });
    const event = new MouseEvent(eventType, { bubbles: true, cancelable: true, button: 0 });
    board.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(true);
    expect(focusedWhileHandling).not.toBe(input);
    expect(document.activeElement).not.toBe(input);
    expect(input.value).toBe('unfinished message');
});

test.each(['touchstart', 'mousedown'])('keeps focus when %s targets the chat input', eventType => {
    input.dispatchEvent(new MouseEvent(eventType, { bubbles: true, button: 0 }));
    expect(document.activeElement).toBe(input);
});

test.each([{ shiftKey: true }, { button: 2 }, { buttons: 2 }])(
    'keeps chat focused while drawing on the board with %j',
    options => {
        board.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, ...options }));
        expect(document.activeElement).toBe(input);
    },
);

test('continues to blur on outside interaction after the chat view is patched', () => {
    chat = patch(chat, chatView(ctrl, 'roundchat'));
    expect(document.getElementById('chat-entry')).toBe(input);
    board.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    expect(document.activeElement).not.toBe(input);
});

test('removing focused chat releases the outside pointer listener', () => {
    const blur = jest.spyOn(input, 'blur');
    chat = patch(chat, h('div#roundchat'));
    board.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    expect(blur).not.toHaveBeenCalled();
});

test('outside clicks leave another focused field alone', () => {
    const other = document.createElement('input');
    document.body.append(other);
    other.focus();
    board.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    expect(document.activeElement).toBe(other);
});
