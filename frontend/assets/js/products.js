(() => {
  const favoriteIds = new Set();
  let favoritesLoaded = false;
  let categoriesCache = null;
  let categoriesCacheExpires = 0;
  let categoriesRequest = null;

  function normalizeProduct(item) {
    const sellerObject = typeof item.seller === "object" && item.seller !== null ? item.seller : null;
    const seller = sellerObject
      ? sellerObject.display_name || sellerObject.name || sellerObject.email || "SokoMtaani seller"
      : item.seller || "Local seller";
    const contacts = item.contact_preferences || sellerObject?.contacts || {};
    const photos = item.images || item.product_images || [];
    return {
      ...item,
      id: item.id || item.uuid,
      name: item.name || item.title || "Marketplace listing",
      price: Number(item.price || 0),
      oldPrice: Number(item.old_price || item.original_price || item.oldPrice || 0) || undefined,
      category: typeof item.category === "object" ? item.category.name : item.category || "Marketplace",
      condition: ({
        new: "New",
        like_new: "Like new",
        gently_used: "Gently used",
      })[String(item.condition || "").toLowerCase()] || item.condition || "Condition not specified",
      county: item.county || "",
      town: item.town || item.neighbourhood || "",
      seller,
      seller_id: item.seller_id || sellerObject?.id || "",
      contact_preferences: contacts,
      phone: item.phone || contacts.phone || "",
      contact_email: item.contact_email || contacts.email || "",
      telegram_username: item.telegram_username || contacts.telegram || "",
      rating: Number(item.seller_rating || item.rating || 0),
      reviews: Number(item.seller_review_count || item.reviews || 0),
      posted: item.posted || item.published_at || "Recently listed",
      image: item.image || item.primary_image || (typeof photos[0] === "string" ? photos[0] : photos[0]?.image || photos[0]?.url) || "",
      views: Number(item.views || item.view_count || 0),
      enquiries: Number(item.enquiries || item.enquiry_count || 0),
      popular: Number(item.popular || item.view_count || 0),
      negotiable: Boolean(item.negotiable),
      verified: Boolean(item.seller_verified || item.verified),
    };
  }

  function getFavorites() {
    return [...favoriteIds];
  }

  function clearFavorites() {
    favoriteIds.clear();
    favoritesLoaded = false;
  }

  async function favorites() {
    const response = await window.SokoApi.request("favourites/");
    const products = (response.data.results || response.data)
      .map((item) => item.product_detail || item.product)
      .filter((item) => item && typeof item === "object")
      .map(normalizeProduct);
    favoriteIds.clear();
    products.forEach((product) => favoriteIds.add(String(product.id)));
    favoritesLoaded = true;
    return products;
  }

  async function toggleFavorite(id) {
    if (!favoritesLoaded) await favorites();
    const key = String(id);
    if (favoriteIds.has(key)) {
      await window.SokoApi.request(`favourites/${encodeURIComponent(id)}/`, { method: "DELETE" });
      favoriteIds.delete(key);
      return false;
    }
    await window.SokoApi.request("favourites/", { method: "POST", body: { product: id } });
    favoriteIds.add(key);
    return true;
  }

  async function list(params = {}) {
    const response = await window.SokoApi.request("products/", { query: params });
    const data = response.data;
    const results = Array.isArray(data) ? data : data.results || [];
    return {
      count: Array.isArray(data) ? data.length : data.count ?? results.length,
      next: Array.isArray(data) ? null : data.next,
      previous: Array.isArray(data) ? null : data.previous,
      results: results.map(normalizeProduct),
    };
  }

  async function get(id) {
    return normalizeProduct((await window.SokoApi.request(`products/${encodeURIComponent(id)}/`)).data);
  }

  async function sellerProfile(name) {
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(name)) {
      try {
        return (await window.SokoApi.request(`sellers/${encodeURIComponent(name)}/`)).data;
      } catch (error) {
        if (error.status === 404) return null;
        throw error;
      }
    }
    const response = await window.SokoApi.request("sellers/", { query: { search: name } });
    const sellers = response.data.results || response.data;
    const normalizedName = String(name).toLowerCase();
    return sellers.find((seller) =>
      String(seller.slug || seller.display_name || seller.name).toLowerCase() === normalizedName
    ) || null;
  }

  async function sellerItems(seller) {
    const response = await window.SokoApi.request("products/", {
      query: { seller, page_size: 20 },
    });
    return (response.data.results || response.data).map(normalizeProduct);
  }

  async function categories() {
    if (categoriesCache && Date.now() < categoriesCacheExpires) return categoriesCache;
    if (categoriesRequest) return categoriesRequest;
    categoriesRequest = window.SokoApi.request("categories/")
      .then(({ data }) => {
        categoriesCache = data.results || data;
        categoriesCacheExpires = Date.now() + 60_000;
        return categoriesCache;
      })
      .finally(() => {
        categoriesRequest = null;
      });
    return categoriesRequest;
  }

  async function listComments(id) {
    const response = await window.SokoApi.request(`products/${encodeURIComponent(id)}/comments/`);
    return response.data.results || response.data;
  }

  async function addComment(id, content) {
    return (await window.SokoApi.request(`products/${encodeURIComponent(id)}/comments/`, {
      method: "POST",
      body: { content },
    })).data;
  }

  async function addSellerReview(id, values) {
    return (await window.SokoApi.request(`sellers/${encodeURIComponent(id)}/reviews/`, {
      method: "POST",
      body: values,
    })).data;
  }

  async function sellerReviews(id) {
    const response = await window.SokoApi.request(`sellers/${encodeURIComponent(id)}/reviews/`);
    return response.data.results || response.data;
  }

  async function voteComment(productId, commentId) {
    return window.SokoApi.request(
      `products/${encodeURIComponent(productId)}/comments/${encodeURIComponent(commentId)}/helpful/`,
      { method: "POST" },
    );
  }

  async function reportContent(targetType, targetId) {
    return window.SokoApi.request("reports/", {
      method: "POST",
      body: { target_type: targetType, target_id: targetId, reason: "other" },
    });
  }

  async function create(payload) {
    return (await window.SokoApi.request("products/", { method: "POST", body: payload })).data;
  }

  async function update(id, payload) {
    return (await window.SokoApi.request(`products/${encodeURIComponent(id)}/`, {
      method: "PATCH",
      body: payload,
    })).data;
  }

  async function updateStatus(id, status) {
    return (await window.SokoApi.request(`products/${encodeURIComponent(id)}/availability/`, {
      method: "POST",
      body: { status },
    })).data;
  }

  window.SokoProducts = {
    addComment,
    addSellerReview,
    categories,
    clearFavorites,
    create,
    favorites,
    get,
    getFavorites,
    list,
    listComments,
    normalize: normalizeProduct,
    reportContent,
    sellerItems,
    sellerProfile,
    sellerReviews,
    toggleFavorite,
    update,
    updateStatus,
    voteComment,
  };
})();
