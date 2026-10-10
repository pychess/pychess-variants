import { h, VNode } from 'snabbdom';

import { patch } from './document';

interface AlertDialogOptions {
    title?: string;
    text: string;
    okText?: string;
}

let dialogVNode: VNode | null = null;
let pendingResolve: (() => void) | null = null;

// Native like confirmDialog, so an alert raised from inside a modal <dialog> shows above it.
function ensureDialogElement(): HTMLDialogElement {
    const existing = document.getElementById('alert-dialog');
    if (existing instanceof HTMLDialogElement) return existing;
    existing?.remove();

    const dialogElement = document.createElement('dialog');
    dialogElement.id = 'alert-dialog';
    dialogElement.className = 'alert-dialog-root alert-dialog-native';
    dialogElement.addEventListener('cancel', event => {
        event.preventDefault();
        closeDialog();
    });
    dialogElement.addEventListener('click', event => {
        if (event.target === dialogElement) closeDialog();
    });
    document.body.appendChild(dialogElement);
    return dialogElement;
}

function closeDialog(): void {
    const dialogElement = document.getElementById('alert-dialog');
    if (dialogElement instanceof HTMLDialogElement && dialogElement.open) dialogElement.close();
    dialogVNode = null;

    if (pendingResolve) {
        const resolve = pendingResolve;
        pendingResolve = null;
        resolve();
    }
}

function renderDialog(options: AlertDialogOptions): void {
    const dialogElement = ensureDialogElement();
    const currentElm = dialogVNode?.elm as Node | undefined;
    if (dialogVNode !== null && (!currentElm || !document.contains(currentElm))) {
        dialogVNode = null;
    }

    const contentChildren: VNode[] = [];
    if (options.title) {
        contentChildren.push(h('h2', options.title));
    }
    contentChildren.push(h('p', options.text));
    contentChildren.push(
        h('div.alert-dialog-actions', [
            h(
                'button.button.alert-dialog-ok',
                {
                    props: { type: 'button' },
                    on: {
                        click: () => closeDialog(),
                    },
                },
                options.okText || 'OK',
            ),
        ]),
    );

    const vnode = h('div.alert-dialog-content', contentChildren);

    if (dialogVNode === null) {
        dialogElement.innerHTML = '';
        const placeholder = document.createElement('div');
        dialogElement.appendChild(placeholder);
        dialogVNode = patch(placeholder, vnode);
    } else {
        dialogVNode = patch(dialogVNode, vnode);
    }

    if (!dialogElement.open) dialogElement.showModal();
    window.requestAnimationFrame(() => {
        const okButton = dialogElement.querySelector('.alert-dialog-ok') as HTMLButtonElement | null;
        if (okButton) okButton.focus();
    });
}

export function alertDialog(options: AlertDialogOptions): Promise<void> {
    if (pendingResolve) {
        const resolve = pendingResolve;
        pendingResolve = null;
        resolve();
    }

    renderDialog(options);

    return new Promise<void>(resolve => {
        pendingResolve = resolve;
    });
}
