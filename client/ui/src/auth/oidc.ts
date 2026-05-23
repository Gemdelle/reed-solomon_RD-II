/**
 * OIDC integration using oidc-client-ts.
 * The server returns the provider config via GET /auth/config.
 * When oidc_enabled=true, the UI uses this module to do the auth code flow.
 * The peer_id is derived from the JWT `sub` claim after login.
 */
import { UserManager, type UserManagerSettings, type User } from "oidc-client-ts";

let _manager: UserManager | null = null;

export function initOidc(issuer: string, clientId: string, redirectUri: string): UserManager {
  const settings: UserManagerSettings = {
    authority: issuer,
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: "openid profile email",
    post_logout_redirect_uri: redirectUri,
    automaticSilentRenew: true,
  };
  _manager = new UserManager(settings);
  return _manager;
}

export function getManager(): UserManager | null {
  return _manager;
}

export async function startLogin(): Promise<void> {
  if (!_manager) throw new Error("OIDC not initialized");

  if (window.rsAgent?.openExternal) {
    // Loopback flow for Electron: generate the authorization URL (stores PKCE
    // state/nonce/code_verifier in renderer sessionStorage for later validation),
    // then open it in the default system browser.
    // handleLoopback() polls the agent's /auth/callback and completes the exchange.
    const req = await (_manager as any)._client.createSigninRequest({ request_type: "si:r" });
    window.rsAgent.openExternal(req.url);
  } else {
    await _manager.signinRedirect();
  }
}

/** Handles the redirect callback. Returns the authenticated user. */
export async function handleCallback(url?: string): Promise<User> {
  if (!_manager) throw new Error("OIDC not initialized");
  const user = await _manager.signinCallback(url);
  if (!user) throw new Error("OIDC callback returned no user");
  return user;
}

/** Polls the agent for the auth code (Loopback flow). */
export async function handleLoopback(): Promise<User> {
  if (!_manager) throw new Error("OIDC not initialized");
  
  const agentUrl = window.rsAgent?.baseUrl ?? "http://localhost:8000";
  
  // Poll every 1s for the code
  while (true) {
    try {
      const res = await fetch(`${agentUrl}/auth/poll`);
      const data = await res.json();
      if (data && data.code) {
        // Construct the full callback URL for the library to parse
        const callbackUrl = `${(_manager as any).settings.redirect_uri}?code=${data.code}&state=${data.state}`;
        return await handleCallback(callbackUrl);
      }
    } catch (e) {
      console.error("Polling error:", e);
    }
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
}

/** Returns the current user from the session store. */
export async function getUser(): Promise<User | null> {
  if (!_manager) return null;
  return _manager.getUser();
}

export async function logout(): Promise<void> {
  if (!_manager) return;
  await _manager.signoutRedirect();
}
