(function () {
  'use strict';

  function normalize(input) {
    if (typeof input !== 'string') return '';
    const compact = input.normalize('NFKC').replace(/[\s-]/g, '');
    const match = /^(?:\+86|0086|86)?(1[3-9]\d{9})$/.exec(compact);
    return match ? '+86' + match[1] : '';
  }

  function requirePhone(input) {
    const phone = normalize(input);
    if (!phone) throw new Error('请输入有效的中国大陆手机号');
    return phone;
  }

  async function send(client, input) {
    return client.auth.signInWithOtp({
      phone: requirePhone(input),
      options: { channel: 'sms', shouldCreateUser: true }
    });
  }

  function requireToken(code) {
    const token = typeof code === 'string' ? code.trim() : '';
    if (!/^\d{6,10}$/.test(token)) throw new Error('请输入短信中的数字验证码');
    return token;
  }

  async function verify(client, input, code) {
    return client.auth.verifyOtp({ phone: requirePhone(input), token: requireToken(code), type: 'sms' });
  }

  async function sendBinding(client, input) {
    return client.auth.updateUser({ phone: requirePhone(input) });
  }

  async function verifyBinding(client, input, code) {
    return client.auth.verifyOtp({ phone: requirePhone(input), token: requireToken(code), type: 'phone_change' });
  }

  window.LR_PHONE = { normalize, send, verify, sendBinding, verifyBinding };
})();
