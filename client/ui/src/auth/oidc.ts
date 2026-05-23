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

/** Starts the OIDC redirect flow. */
export async function startLogin(): Promise<void> {
  if (!_manager) throw new Error("OIDC not initialized");
  await _manager.signinRedirect();
}

/** Handles the redirect callback. Returns the authenticated user. */
export async function handleCallback(): Promise<User> {
  if (!_manager) throw new Error("OIDC not initialized");
  const user = await _manager.signinCallback();
  if (!user) throw new Error("OIDC callback returned no user");
  return user;
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
