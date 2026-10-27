/** Observe only the caller-selected Ego Page. No cookies, storage or page text returned. */
export async function observeSession(task, page, binding, oracle) {
  if (binding.provider !== 'ego-lite' || String(task.spaceId) !== binding.session ||
      page.label !== binding.page) throw new Error('session-mismatch');
  // Require an explicit business origin and positive/negative UI oracle.
  const origin = new URL(oracle.origin);
  if (!['http:', 'https:'].includes(origin.protocol) || origin.origin !== oracle.origin ||
      !oracle.authenticatedSelector || !oracle.loginSelector) throw new Error('invalid-oracle');
  const current = new URL(await page.url());
  if (current.origin !== origin.origin) {
    return sessionObservation(binding, false, 'unknown');
  }
  const state = await page.evaluate(({ authenticatedSelector, loginSelector }) => {
    const visible = (selector) => {
      const element = document.querySelector(selector);
      if (!element) return false;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
    };
    return { positive: visible(authenticatedSelector), login: visible(loginSelector) };
  }, { authenticatedSelector: oracle.authenticatedSelector, loginSelector: oracle.loginSelector });
  return sessionObservation(binding, true,
    state.positive && !state.login ? 'authenticated' :
      state.login && !state.positive ? 'required' : 'unknown');
}

function sessionObservation(binding, targetConfirmed, authentication) {
  return Object.fromEntries([
    ...['provider', 'session', 'page', 'profile', 'target'].map(key => [key, binding[key]]),
    ['connection', 'connected'], ['target_confirmed', targetConfirmed],
    ['authentication', authentication],
  ]);
}

/** Bounded static signals from the selected, explicitly allowed page; no requests. */
export async function collectStaticSignals(page, allowedOrigins) {
  const current = new URL(await page.url());
  if (!Array.isArray(allowedOrigins) || !allowedOrigins.includes(current.origin)) {
    throw new Error('static-target-unconfirmed');
  }
  return page.evaluate(() => {
    const count = selector => document.querySelectorAll(selector).length;
    // Counts and fixed labels only: no form values, HTML, text, URLs or storage.
    return {
      schema_version: 1,
      source: 'current-document',
      forms: count('form'),
      password_fields: count('input[type="password"]'),
      scripts: count('script[src]'),
      stylesheets: count('link[rel="stylesheet"]'),
      frames: count('iframe'),
      meta_refresh: count('meta[http-equiv="refresh" i]') > 0,
      limitations: ['no-network-history', 'no-cross-origin-frame-content',
        'no-authentication-verdict', 'no-anti-bot-verdict'],
    };
  });
}
