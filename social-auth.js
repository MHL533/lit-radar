window.LR_SOCIAL = {
  async start(client, provider, link) {
    if (typeof provider !== 'string' || !provider.startsWith('custom:') || provider.length === 7) {
      throw new Error('该登录方式尚未配置。');
    }
    if (typeof link !== 'boolean') throw new Error('请选择登录或绑定操作。');
    const redirectTo = new URL('./', window.location.href);
    const request = { provider, options: { redirectTo: redirectTo.href } };
    return link ? client.auth.linkIdentity(request) : client.auth.signInWithOAuth(request);
  }
};
