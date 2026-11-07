(() => {
  const config = window.SOKO_CONFIG;

  class ApiError extends Error {
    constructor(message, status = 0, data = null) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.data = data;
    }
  }

  async function getCsrfToken() {
    let response;
    try {
      response = await fetch(`${config.API_BASE_URL}/auth/csrf/`, {
        credentials: "include",
        cache: "no-store",
        signal: AbortSignal.timeout(config.REQUEST_TIMEOUT_MS),
      });
    } catch (error) {
      if (error.name === "TimeoutError") throw new ApiError("The server took too long to respond.");
      throw new ApiError("Could not start a secure session. Check that the API is running.");
    }
    if (!response.ok) throw new ApiError("Could not start a secure session.", response.status);
    const data = await response.json();
    if (!data.csrfToken) throw new ApiError("The API did not provide a CSRF token.", response.status, data);
    return data.csrfToken;
  }

  async function request(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const url = new URL(`${config.API_BASE_URL.replace(/\/$/, "")}/${path.replace(/^\//, "")}`);
    if (options.query) {
      Object.entries(options.query).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
          url.searchParams.set(key, String(value));
        }
      });
    }

    const headers = new Headers(options.headers || {});
    let body;
    if (options.body instanceof FormData) {
      body = options.body;
    } else if (options.body !== undefined) {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(options.body);
    }

    if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
      headers.set("X-CSRFToken", await getCsrfToken());
    }

    let response;
    try {
      response = await fetch(url, {
        method,
        headers,
        body,
        credentials: "include",
        cache: "no-store",
        signal: AbortSignal.timeout(config.REQUEST_TIMEOUT_MS),
      });
    } catch (error) {
      if (error.name === "TimeoutError") throw new ApiError("The server took too long to respond.");
      if (error.name === "AbortError") throw new ApiError("The request was cancelled.");
      throw new ApiError("Could not reach the SokoMtaani API. Check the server and network.");
    }

    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok) {
      const message = data?.detail || Object.values(data || {}).flat().find((item) => typeof item === "string")
        || `Request failed (${response.status}).`;
      throw new ApiError(message, response.status, data);
    }
    return { status: response.status, data };
  }

  window.SokoApi = {
    ApiError,
    request,
  };
})();
