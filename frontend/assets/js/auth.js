(() => {
  let pendingMfa = null;
  let currentUserCache = null;
  let currentUserLoaded = false;
  let currentUserRequest = null;

  function setCurrentUser(user) {
    currentUserCache = user;
    currentUserLoaded = true;
    currentUserRequest = null;
  }

  function normalizeUser(user) {
    const first = user.first_name || user.firstName || "";
    const last = user.last_name || user.lastName || "";
    return {
      ...user,
      first_name: first,
      last_name: last,
      displayName: [first, last].filter(Boolean).join(" ") || user.email?.split("@")[0] || "SokoMtaani member",
      initials: [first[0], last[0]].filter(Boolean).join("").toUpperCase() || user.email?.slice(0, 1).toUpperCase() || "S",
    };
  }

  async function register(fields) {
    return window.SokoApi.request("auth/register/", { method: "POST", body: fields });
  }

  async function login(fields) {
    const result = await window.SokoApi.request("auth/login/", { method: "POST", body: fields });
    if (result.status === 202) {
      pendingMfa = result.data;
      return result;
    }
    const user = normalizeUser(result.data);
    setCurrentUser(user);
    return { ...result, data: user };
  }

  async function verifyMfa(code) {
    const result = await window.SokoApi.request("auth/mfa/verify/", { method: "POST", body: { code } });
    pendingMfa = null;
    const user = normalizeUser(result.data);
    setCurrentUser(user);
    return { ...result, data: user };
  }

  async function logout() {
    await window.SokoApi.request("auth/logout/", { method: "POST" });
    window.SokoProducts.clearFavorites();
    setCurrentUser(null);
  }

  async function currentUser() {
    if (currentUserLoaded) return currentUserCache;
    if (currentUserRequest) return currentUserRequest;
    currentUserRequest = (async () => {
      try {
        const result = await window.SokoApi.request("auth/me/");
        const user = normalizeUser(result.data);
        setCurrentUser(user);
        return user;
      } catch (error) {
        if (error.status === 401 || error.status === 403) {
          setCurrentUser(null);
          return null;
        }
        currentUserRequest = null;
        throw error;
      }
    })();
    return currentUserRequest;
  }

  async function requestPasswordReset(email) {
    return window.SokoApi.request("auth/password-reset/", { method: "POST", body: { email } });
  }

  async function confirmPasswordReset(values) {
    return window.SokoApi.request("auth/password-reset/confirm/", { method: "POST", body: values });
  }

  async function changePassword(values) {
    return window.SokoApi.request("auth/password-change/", { method: "POST", body: values });
  }

  async function activateSeller(values = {}) {
    const result = await window.SokoApi.request("sellers/activate/", {
      method: "POST",
      body: values,
    });
    const user = normalizeUser(result.data.user || result.data);
    setCurrentUser(user);
    return user;
  }

  async function verifyEmail(token) {
    return window.SokoApi.request("auth/email-verification/", { method: "POST", body: { token } });
  }

  async function resendVerification(email) {
    return window.SokoApi.request("auth/email-verification/resend/", { method: "POST", body: { email } });
  }

  window.SokoAuth = {
    activateSeller,
    changePassword,
    confirmPasswordReset,
    currentUser,
    getPendingMfa: () => pendingMfa,
    login,
    logout,
    register,
    requestPasswordReset,
    resendVerification,
    verifyEmail,
    verifyMfa,
  };
})();
