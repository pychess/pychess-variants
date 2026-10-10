const CSRF_FORM_FIELD = '_csrf_token';
const CSRF_HEADER = 'X-CSRF-Token';
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function requestMethod(input: RequestInfo | URL, init?: RequestInit): string {
    if (init?.method) return init.method.toUpperCase();
    if (typeof Request !== 'undefined' && input instanceof Request) return input.method.toUpperCase();
    return 'GET';
}

function requestUrl(input: RequestInfo | URL): URL | null {
    try {
        if (typeof Request !== 'undefined' && input instanceof Request) return new URL(input.url, window.location.href);
        if (input instanceof URL) return input;
        if (typeof input === 'string') return new URL(input, window.location.href);
        return new URL(String(input), window.location.href);
    } catch {
        return null;
    }
}

function formAction(form: HTMLFormElement): URL | null {
    try {
        return new URL(form.action || window.location.href, window.location.href);
    } catch {
        return null;
    }
}

function addTokenToForm(form: HTMLFormElement, token: string): void {
    const method = (form.method || 'get').toUpperCase();
    const action = formAction(form);
    if (!UNSAFE_METHODS.has(method) || !action || action.origin !== window.location.origin) return;

    const existing = form.elements.namedItem(CSRF_FORM_FIELD);
    let input = existing instanceof HTMLInputElement ? existing : null;
    if (input === null) {
        input = document.createElement('input');
        input.type = 'hidden';
        input.name = CSRF_FORM_FIELD;
        form.appendChild(input);
    }
    input.value = token;
}

export function installCsrfProtection(root: HTMLElement | null): void {
    const token = root?.getAttribute('data-csrf-token') ?? '';
    if (!token) return;

    const originalFetch = window.fetch.bind(window);
    window.fetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
        const method = requestMethod(input, init);
        const url = requestUrl(input);
        if (!UNSAFE_METHODS.has(method) || !url || url.origin !== window.location.origin) {
            return originalFetch(input, init);
        }

        const requestHeaders = typeof Request !== 'undefined' && input instanceof Request ? input.headers : undefined;
        const headers = new Headers(requestHeaders);
        if (init?.headers) {
            new Headers(init.headers).forEach((value, key) => headers.set(key, value));
        }
        if (!headers.has(CSRF_HEADER)) headers.set(CSRF_HEADER, token);
        return originalFetch(input, { ...init, headers });
    };

    document.addEventListener(
        'submit',
        event => {
            if (event.target instanceof HTMLFormElement) addTokenToForm(event.target, token);
        },
        true,
    );

    document.querySelectorAll<HTMLFormElement>('form').forEach(form => addTokenToForm(form, token));
}
