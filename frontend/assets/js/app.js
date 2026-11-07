(() => {
  const main = document.getElementById("app-main");
  const header = document.getElementById("site-header");
  const footer = document.getElementById("site-footer");
  const toastRegion = document.getElementById("toast-region");
  let activeConversation = "";
  let pendingProductImages = [];
  let currentRoute = null;
  const comments = new Map();
  const sellerReviews = new Map();
  const savedPrivacy = { email: true, messages: true, priceChanges: true };
  let siteInfoCache = null;
  let siteInfoRequest = null;
  let appInitialized = false;
  let routeVersion = 0;
  let renderedRouteVersion = 0;
  let routeRendering = false;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const create = (tag, className = "", text = "") => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== "") node.textContent = text;
    return node;
  };
  const icon = (name) => {
    const node = create("i", `bi ${name}`);
    node.setAttribute("aria-hidden", "true");
    return node;
  };
  const safeText = (value) => String(value ?? "");
  const routeHref = (path) => `#${path.startsWith("/") ? path : `/${path}`}`;
  const isAdmin = (user) => Boolean(user?.admin_role && user.admin_role !== "");
  const adminHome = (user) => user?.admin_role === "super_admin"
    ? "/admin"
    : user?.admin_role === "support_admin" ? "/admin/users" : "/admin/reports";
  function safeMediaUrl(value) {
    if (typeof value !== "string" || !value.trim()) return "assets/images/listing-placeholder.svg";
    try {
      const url = new URL(value, location.href);
      return ["https:", "http:", "blob:"].includes(url.protocol) ? url.href : "assets/images/listing-placeholder.svg";
    } catch {
      return "assets/images/listing-placeholder.svg";
    }
  }
  function setMediaSource(image, source) {
    image.addEventListener("error", () => {
      if (!image.src.endsWith("/assets/images/listing-placeholder.svg")) {
        image.src = "assets/images/listing-placeholder.svg";
      }
    }, { once: true });
    image.src = safeMediaUrl(source);
  }
  const currency = (amount) => new Intl.NumberFormat("en-KE", {
    style: "currency", currency: "KES", maximumFractionDigits: 0,
  }).format(Number(amount) || 0);

  function showToast(message, type = "success") {
    const toast = create("div", `toast-message${type === "error" ? " error" : ""}`, message);
    toastRegion.append(toast);
    window.setTimeout(() => toast.remove(), 3600);
  }

  function showError(error) {
    showToast(error?.message || "Something went wrong. Please try again.", "error");
  }

  function parseRoute() {
    let path;
    let query;
    if (location.hash.startsWith("#/")) {
      const raw = location.hash.slice(1);
      const cut = raw.indexOf("?");
      path = cut === -1 ? raw : raw.slice(0, cut);
      query = new URLSearchParams(cut === -1 ? "" : raw.slice(cut + 1));
    } else {
      path = location.pathname.replace(/\/+$/, "") || "/";
      query = new URLSearchParams(location.search);
      if (path === "/index.html" || path === "/") path = "/home";
    }
    return { path, query };
  }

  function navigate(path) {
    location.hash = path.startsWith("#") ? path.slice(1) : path;
  }

  function appendAll(parent, children) {
    children.forEach((child) => child && parent.append(child));
    return parent;
  }

  function brandLink() {
    const link = create("a", "brand");
    link.href = routeHref("/home");
    const mark = create("img");
    mark.src = "assets/images/brand-mark.svg";
    mark.alt = "";
    const name = create("span");
    name.append(document.createTextNode("Soko"));
    name.append(Object.assign(create("b"), { textContent: "Mtaani" }));
    return appendAll(link, [mark, name]);
  }

  async function renderHeader(user) {
    header.className = "site-header";
    const wrap = create("div", "container-wide");
    const top = create("div", "header-main");
    top.append(brandLink());

    const search = create("form", "top-search");
    search.id = "top-search-form";
    search.setAttribute("role", "search");
    const searchInput = create("input");
    searchInput.name = "search";
    searchInput.placeholder = "Find something good...";
    searchInput.setAttribute("aria-label", "Search listings");
    const route = parseRoute();
    searchInput.value = route.query.get("search") || route.query.get("keyword") || "";
    const searchButton = create("button");
    searchButton.type = "submit";
    searchButton.setAttribute("aria-label", "Search");
    searchButton.append(icon("bi-search"));
    search.append(searchInput, searchButton);
    top.append(search);

    const links = create("nav", "top-links");
    links.setAttribute("aria-label", "Main navigation");
    [
      ["/search", "Explore", ""],
      ["/about", "Our story", "optional"],
    ].forEach(([path, label, klass]) => {
      const link = create("a", klass);
      link.href = routeHref(path);
      link.textContent = label;
      links.append(link);
    });
    top.append(links);

    const actions = create("div", "header-actions");
    if (user) {
      const dashboardPath = isAdmin(user) ? adminHome(user) : user.role === "seller" ? "/seller" : "/buyer";
      const account = create("a", "btn btn-outline btn-small");
      account.href = routeHref(dashboardPath);
      const avatar = create("span", "avatar", user.initials);
      account.append(avatar, document.createTextNode("My account"));
      actions.append(account);
      const logout = create("button", "icon-btn");
      logout.type = "button";
      logout.dataset.action = "logout";
      logout.title = "Sign out";
      logout.setAttribute("aria-label", "Sign out");
      logout.append(icon("bi-box-arrow-right"));
      actions.append(logout);
    } else {
      const login = create("a", "btn btn-outline btn-small");
      login.href = routeHref("/login");
      login.textContent = "Log in";
      const register = create("a", "btn btn-primary btn-small");
      register.href = routeHref("/register");
      register.textContent = "Join free";
      actions.append(login, register);
    }
    const menuButton = create("button", "icon-btn header-menu");
    menuButton.type = "button";
    menuButton.dataset.action = "mobile-menu";
    menuButton.setAttribute("aria-label", "Show categories");
    menuButton.append(icon("bi-list"));
    actions.append(menuButton);
    top.append(actions);
    wrap.append(top);

    const categoryNav = create("nav", "subnav");
    categoryNav.setAttribute("aria-label", "Categories");
    const all = create("a");
    all.href = routeHref("/search");
    all.textContent = "All categories";
    categoryNav.append(all);
    const categories = await window.SokoProducts.categories();
    categories.forEach((item) => {
      const link = create("a");
      link.href = routeHref(`/category/${encodeURIComponent(item.name)}`);
      link.textContent = item.name;
      categoryNav.append(link);
    });
    wrap.append(categoryNav);
    header.replaceChildren();
    header.append(wrap);
  }

  function renderFooter() {
    footer.className = "footer";
    footer.innerHTML = `
      <div class="container-wide">
        <div class="footer-grid">
          <div>
            <a class="brand" href="#/home"><img src="assets/images/brand-mark.svg" alt=""><span>Soko<b>Mtaani</b></span></a>
            <p class="footer-about">Good finds, closer to home. A community marketplace connecting people across Kenya.</p>
            <span class="chip"><i class="bi bi-geo-alt"></i> Made for Kenya</span>
          </div>
          <div><h3>Discover</h3><div class="footer-links">
            <a href="#/search">Browse listings</a><a href="#/search?sort=popular">Popular finds</a><a href="#/safety">Buyer safety</a>
          </div></div>
          <div><h3>Community</h3><div class="footer-links">
            <a href="#/about">About SokoMtaani</a><a href="#/contact">Contact us</a><a href="#/register">Start selling</a><a href="#/messages">Messages</a>
          </div></div>
          <div><h3>Good to know</h3><div class="footer-links">
            <a href="#/terms">Terms of service</a><a href="#/privacy">Privacy policy</a><a href="#/help">Help centre</a><a href="#/settings">Privacy settings</a>
          </div></div>
        </div>
        <div class="footer-bottom"><span>© ${new Date().getFullYear()} SokoMtaani. Made with care in Kenya.</span><span>People first. Neighbourhood always.</span></div>
      </div>`;
  }

  function productCard(product) {
    const card = create("article", "product-card");
    const imageWrap = create("a", "product-image-wrap");
    imageWrap.href = routeHref(`/product/${encodeURIComponent(product.id)}`);
    const image = create("img", "product-image");
    setMediaSource(image, product.image);
    image.alt = product.name;
    image.loading = "lazy";
    imageWrap.append(image);
    const condition = create("span", "tag", product.condition);
    imageWrap.append(condition);
    const favorite = create("button", `favorite-btn${window.SokoProducts.getFavorites().includes(String(product.id)) ? " is-favorite" : ""}`);
    favorite.type = "button";
    favorite.dataset.action = "favorite";
    favorite.dataset.id = product.id;
    favorite.setAttribute("aria-label", "Save listing");
    favorite.setAttribute("aria-pressed", String(window.SokoProducts.getFavorites().includes(String(product.id))));
    favorite.append(icon(window.SokoProducts.getFavorites().includes(String(product.id)) ? "bi-heart-fill" : "bi-heart"));
    imageWrap.append(favorite);
    card.append(imageWrap);

    const content = create("div", "product-content");
    content.append(create("div", "product-category", product.category));
    if (product.admin_created) content.append(create("span", "tag", "Added by SokoMtaani admin"));
    const name = create("a", "product-name", product.name);
    name.href = imageWrap.href;
    content.append(name);
    const price = create("div", "product-price");
    price.append(document.createTextNode(currency(product.price)));
    if (product.oldPrice) price.append(Object.assign(create("s"), { textContent: currency(product.oldPrice) }));
    content.append(price);
    const meta = create("div", "product-meta");
    meta.append(
      appendAll(create("span"), [icon("bi-geo-alt"), document.createTextNode(`${product.town}, ${product.county}`)]),
      appendAll(create("span"), [icon("bi-clock"), document.createTextNode(product.posted)]),
    );
    content.append(meta);
    const seller = create("div", "seller-line");
    seller.append(
      create("span", "avatar", initials(product.seller)),
      create("span", "seller-name", product.seller),
      Object.assign(create("span", "rating"), { textContent: `★ ${product.rating.toFixed(1)}` }),
    );
    content.append(seller);
    card.append(content);
    return card;
  }

  function initials(name = "") {
    return String(name).split(/\s+/).slice(0, 2).map((part) => part[0] || "").join("").toUpperCase();
  }

  function productGrid(products, compact = false) {
    if (!products.length) {
      const empty = create("div", "empty-state");
      empty.append(icon("bi-search"));
      empty.append(create("h3", "", "No listings found just yet"));
      empty.append(create("p", "", "Try changing your search or clearing one of the filters."));
      const clear = create("a", "btn btn-outline btn-small");
      clear.href = routeHref("/search");
      clear.textContent = "Clear filters";
      empty.append(clear);
      return empty;
    }
    const grid = create("div", `product-grid${compact ? " compact" : ""}`);
    products.forEach((product) => grid.append(productCard(product)));
    return grid;
  }

  function sectionHeader(title, subtitle, linkPath = "/search", linkLabel = "See all") {
    const head = create("div", "section-head");
    const left = create("div");
    left.append(create("h2", "", title));
    if (subtitle) left.append(create("p", "", subtitle));
    head.append(left);
    const link = create("a", "text-link");
    link.href = routeHref(linkPath);
    link.append(document.createTextNode(linkLabel), icon("bi-arrow-right"));
    head.append(link);
    return head;
  }

  async function renderCategories() {
    const grid = create("div", "category-grid");
    const categories = await window.SokoProducts.categories();
    categories.forEach((category) => {
      const tile = create("a", "category-tile");
      tile.href = routeHref(`/category/${encodeURIComponent(category.name || category.title)}`);
      const categoryIcon = create("span", "category-icon");
      categoryIcon.append(icon(category.icon || "bi-tag"));
      tile.append(categoryIcon, create("strong", "", category.name || category.title), create("small", "", `${category.product_count ?? category.count ?? 0} items`));
      grid.append(tile);
    });
    return grid;
  }

  async function renderHome() {
    const wrap = create("div");
    const hero = create("section", "hero");
    const inner = create("div", "container-wide");
    const grid = create("div", "hero-grid");
    const copy = create("div");
    copy.append(create("span", "eyebrow", "A little closer to home"));
    const title = create("h1");
    title.append(document.createTextNode("Good finds, "));
    title.append(Object.assign(create("em"), { textContent: "closer to home." }));
    copy.append(title);
    copy.append(create("p", "hero-copy", "Discover pre-loved treasures, everyday essentials and local makers — all from people and places around you."));
    const form = create("form", "hero-search");
    form.id = "hero-search-form";
    const field = create("label", "search-field");
    field.append(icon("bi-search"));
    const input = create("input");
    input.name = "search";
    input.placeholder = "What are you looking for?";
    input.setAttribute("aria-label", "Search marketplace listings");
    field.append(input);
    const searchButton = create("button", "btn btn-primary");
    searchButton.type = "submit";
    searchButton.append(document.createTextNode("Search"), icon("bi-arrow-right"));
    form.append(field, searchButton);
    copy.append(form);
    const meta = create("div", "hero-meta");
    ["Free to browse", "Local sellers", "No checkout or hidden fees"].forEach((text) => {
      meta.append(appendAll(create("span"), [icon("bi-check-circle-fill"), document.createTextNode(text)]));
    });
    copy.append(meta);
    const art = create("div", "hero-art");
    const photo = create("div", "hero-photo");
    const heroImg = create("img");
    setMediaSource(heroImg, "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=1100&q=85");
    heroImg.alt = "Warm, welcoming living space with locally sourced furniture";
    heroImg.fetchPriority = "high";
    photo.append(heroImg);
    const stamp = create("div", "hero-stamp");
    stamp.append(create("strong", "", "Made for your neighbourhood"));
    art.append(photo, stamp);
    grid.append(copy, art);
    inner.append(grid);
    hero.append(inner);
    wrap.append(hero);

    const announcements = await window.SokoDashboard.announcements();
    if (announcements.length) {
      const notice = create("section", "container-wide announcement-strip");
      announcements.slice(0, 3).forEach((announcement) => {
        notice.append(create("h2", "", announcement.title), create("p", "", announcement.body));
      });
      wrap.append(notice);
    }

    const categoriesSection = create("section", "section container-wide");
    categoriesSection.append(sectionHeader("A good place to start", "A few of the things you can discover around you."));
    categoriesSection.append(await renderCategories());
    wrap.append(categoriesSection);

    const featuredSection = create("section", "section-tight container-wide");
    featuredSection.append(sectionHeader("Lovely finds, lately", "Fresh picks from sellers across Kenya.", "/search?sort=newest"));
    const featured = await window.SokoProducts.list({ sort: "newest" });
    featuredSection.append(productGrid(featured.results.slice(0, 4)));
    wrap.append(featuredSection);

    const trust = create("section", "container-wide section-tight");
    const trustBand = create("div", "trust-band");
    [
      ["bi-people", "Real people, nearby", "Find neighbours, makers and small local businesses."],
      ["bi-chat-heart", "Talk before you decide", "Ask a question and arrange the details directly."],
      ["bi-shield-check", "Your pace, your choice", "Browse freely and make careful, informed decisions."],
    ].forEach(([iconName, titleText, description]) => {
      const item = create("div", "trust-item");
      item.append(icon(iconName));
      const body = create("div");
      body.append(create("strong", "", titleText), create("p", "", description));
      item.append(body);
      trustBand.append(item);
    });
    trust.append(trustBand);
    wrap.append(trust);

    const popularSection = create("section", "section container-wide");
    popularSection.append(sectionHeader("Getting lots of love", "Popular with the SokoMtaani community.", "/search?sort=popular"));
    const popular = await window.SokoProducts.list({ sort: "popular" });
    popularSection.append(productGrid(popular.results.slice(0, 4)));
    wrap.append(popularSection);

    const cta = create("section", "container-wide section-tight");
    cta.innerHTML = `<div class="cta-panel"><div><span class="eyebrow">Have something lovely?</span><h2>Give it a new home.</h2><p>Share what you no longer need with someone who does.</p></div><div class="cta-actions"><a class="btn btn-primary" href="#/seller/create"><i class="bi bi-plus-lg"></i> List an item</a><a class="btn btn-outline" href="#/about">How it works</a></div></div>`;
    wrap.append(cta);
    main.replaceChildren(wrap);
  }

  function makeFilterField(label, control, id) {
    const group = create("div", "filter-group");
    const labelNode = create("label", "", label);
    labelNode.htmlFor = id;
    control.id = id;
    group.append(labelNode, control);
    return group;
  }

  function addSelectOptions(select, values, placeholder) {
    select.append(new Option(placeholder, ""));
    values.forEach((value) => select.append(new Option(value, value)));
  }

  async function renderSearch(query, category) {
    const params = new URLSearchParams(query);
    if (category) params.set("category", category);
    const values = Object.fromEntries(params.entries());
    const result = await window.SokoProducts.list(values);
    const pageWrap = create("div", "container-wide");
    const crumbs = create("div", "breadcrumbs");
    crumbs.append(create("a", "", "Home"), document.createTextNode(" / "));
    const home = crumbs.querySelector("a");
    home.href = routeHref("/home");
    crumbs.append(create("span", "", category || "Explore listings"));
    pageWrap.append(crumbs);
    const heading = create("div");
    heading.append(create("h1", "page-heading", category || "Find something good"), create("p", "", "Good things are closer than you think."));
    pageWrap.append(heading);

    const layout = create("div", "search-layout");
    const filters = create("form", "filter-panel");
    filters.id = "search-filters";
    filters.innerHTML = `<div class="filter-title">Filters <button type="button" class="btn btn-quiet btn-small" data-action="clear-filters">Clear</button></div>`;
    const searchInput = create("input", "form-control");
    searchInput.name = "search";
    searchInput.placeholder = "Try “lamp” or “camera”";
    searchInput.value = values.search || values.keyword || "";
    filters.append(makeFilterField("Keywords", searchInput, "filter-search"));

    const categorySelect = create("select", "form-select");
    categorySelect.name = "category";
    const categories = await window.SokoProducts.categories();
    addSelectOptions(categorySelect, categories.map((item) => item.name || item.title), "All categories");
    categorySelect.value = values.category || "";
    filters.append(makeFilterField("Category", categorySelect, "filter-category"));
    const subcategorySelect = create("select", "form-select");
    subcategorySelect.name = "subcategory";
    const subcategories = categories.flatMap((item) => (item.subcategories || item.children || []).map((child) =>
      typeof child === "string" ? child : child.name || child.title).filter(Boolean));
    addSelectOptions(subcategorySelect, [...new Set(subcategories)], "All subcategories");
    subcategorySelect.value = values.subcategory || "";
    filters.append(makeFilterField("Subcategory", subcategorySelect, "filter-subcategory"));
    const countySelect = create("select", "form-select");
    countySelect.name = "county";
    addSelectOptions(countySelect, window.SOKO_CONFIG.COUNTIES, "All counties");
    countySelect.value = values.county || "";
    filters.append(makeFilterField("County", countySelect, "filter-county"));
    const townInput = create("input", "form-control");
    townInput.name = "town";
    townInput.placeholder = "e.g. Kilimani";
    townInput.value = values.town || "";
    filters.append(makeFilterField("Town or neighbourhood", townInput, "filter-town"));
    const priceRow = create("div", "form-row");
    const minInput = create("input", "form-control");
    minInput.type = "number"; minInput.min = "0"; minInput.name = "min_price"; minInput.placeholder = "Min"; minInput.value = values.min_price || "";
    const maxInput = create("input", "form-control");
    maxInput.type = "number"; maxInput.min = "0"; maxInput.name = "max_price"; maxInput.placeholder = "Max"; maxInput.value = values.max_price || "";
    priceRow.append(minInput, maxInput);
    filters.append(makeFilterField("Price range (KES)", priceRow, "price-range"));
    const condition = create("select", "form-select");
    condition.name = "condition";
    addSelectOptions(condition, ["New", "Like new", "Gently used"], "Any condition");
    condition.value = values.condition || "";
    filters.append(makeFilterField("Condition", condition, "filter-condition"));
    const rating = create("select", "form-select");
    rating.name = "rating";
    [["", "Any seller rating"], ["4", "4 stars & up"], ["4.5", "4.5 stars & up"]].forEach(([value, label]) => rating.append(new Option(label, value)));
    rating.value = values.rating || "";
    filters.append(makeFilterField("Seller rating", rating, "filter-rating"));
    const apply = create("button", "btn btn-primary");
    apply.type = "submit"; apply.textContent = "Show listings";
    filters.append(apply);
    layout.append(filters);

    const content = create("div");
    const resultsHead = create("div", "search-results-head");
    const total = create("strong", "", `${result.count} ${result.count === 1 ? "listing" : "listings"}`);
    const controls = create("div");
    controls.style.display = "flex"; controls.style.gap = "8px"; controls.style.alignItems = "center";
    const filterToggle = create("button", "btn btn-outline btn-small mobile-filter-toggle");
    filterToggle.type = "button"; filterToggle.dataset.action = "toggle-filters";
    filterToggle.append(icon("bi-sliders"), document.createTextNode("Filters"));
    const sort = create("select", "form-select sort-control");
    sort.id = "search-sort";
    [["newest", "Newest first"], ["price_asc", "Price: low to high"], ["price_desc", "Price: high to low"], ["popular", "Most popular"]].forEach(([value, label]) => sort.append(new Option(label, value)));
    sort.value = values.sort || "newest";
    controls.append(filterToggle, sort);
    resultsHead.append(total, controls);
    content.append(resultsHead);
    content.append(productGrid(result.results));
    if (result.count > 9) {
      const pagination = create("nav", "pagination");
      pagination.setAttribute("aria-label", "Search result pages");
      const pages = Math.ceil(result.count / 20);
      for (let page = 1; page <= pages; page += 1) {
        const button = create("button", `${page === Number(values.page || 1) ? "active" : ""}`, String(page));
        button.type = "button"; button.dataset.action = "page"; button.dataset.page = String(page);
        pagination.append(button);
      }
      content.append(pagination);
    }
    layout.append(content);
    pageWrap.append(layout);
    main.replaceChildren(pageWrap);
  }

  function detailStat(iconName, text) {
    return appendAll(create("span"), [icon(iconName), document.createTextNode(text)]);
  }

  async function renderProduct(id) {
    const product = await window.SokoProducts.get(id);
    if (!product) {
      renderNotFound("We couldn’t find that listing.", "It may have been removed or the link may be out of date.");
      return;
    }
    const wrap = create("div", "container-wide");
    const crumbs = create("div", "breadcrumbs");
    const home = create("a", "", "Home"); home.href = routeHref("/home");
    const category = create("a", "", product.category); category.href = routeHref(`/category/${encodeURIComponent(product.category)}`);
    crumbs.append(home, document.createTextNode(" / "), category, document.createTextNode(" / "), create("span", "", product.name));
    wrap.append(crumbs);
    const layout = create("div", "detail-grid");
    const media = create("div");
    const image = create("img", "detail-photo");
    setMediaSource(image, product.image); image.alt = product.name;
    media.append(image);
    const photos = product.images || product.product_images || [];
    const imageUrls = photos.map((photo) => typeof photo === "string" ? photo : photo.image || photo.url).filter(Boolean);
    if (!imageUrls.length && product.image) imageUrls.push(product.image);
    const thumbs = create("div", "detail-thumb-row");
    setMediaSource(image, imageUrls[0] || "");
    image.alt = product.name;
    for (let index = 0; index < imageUrls.length; index += 1) {
      const thumb = create("button", `detail-thumb${index === 0 ? " active" : ""}`);
      thumb.type = "button"; thumb.setAttribute("aria-label", `Product image ${index + 1}`);
      const thumbImage = create("img"); setMediaSource(thumbImage, imageUrls[index]); thumbImage.alt = "";
      thumb.append(thumbImage);
      thumb.addEventListener("click", () => {
        setMediaSource(image, imageUrls[index]);
        setMediaSource(thumbImage, imageUrls[index]);
        thumbs.querySelectorAll(".detail-thumb").forEach((item) => item.classList.toggle("active", item === thumb));
      });
      thumbs.append(thumb);
    }
    if (imageUrls.length > 1) media.append(thumbs);

    const info = create("section", "detail-info");
    info.append(create("span", "eyebrow", product.category));
    info.append(create("h1", "", product.name));
    info.append(create("div", "detail-price", currency(product.price)));
    const stats = create("div", "detail-subline");
    stats.append(detailStat("bi-geo-alt", `${product.town}, ${product.county}`), detailStat("bi-clock", product.posted), detailStat("bi-eye", `${product.views} views`));
    info.append(stats);
    const sellerCard = create("div", "seller-card");
    sellerCard.append(create("span", "avatar", initials(product.seller)));
    const sellerBody = create("div", "seller-card-content");
    const sellerLink = create("a", "", product.seller);
    sellerLink.href = routeHref(`/seller/${encodeURIComponent(product.seller_id || product.seller)}`);
    sellerBody.append(sellerLink, create("small", "", `★ ${product.rating.toFixed(1)} · ${product.reviews} community reviews`));
    sellerCard.append(sellerBody);
    if (product.verified) sellerCard.append(create("span", "chip badge-verified", "Identity checked"));
    info.append(sellerCard);

    const actions = create("div", "contact-actions");
    const message = create("button", "btn btn-primary wide", "Message seller");
    message.type = "button"; message.dataset.action = "message-seller"; message.dataset.product = product.id;
    message.prepend(icon("bi-chat-dots"));
    actions.append(message);
    const addToCart = create("button", "btn btn-outline wide", "Add to cart");
    addToCart.type = "button";
    addToCart.dataset.action = "add-cart-item";
    addToCart.dataset.id = product.id;
    addToCart.prepend(icon("bi-cart3"));
    actions.append(addToCart);
    const contact = product.contact_preferences || product.contact || {};
    const phone = normalKenyanPhone(product.phone || contact.phone);
    if (phone && contact.allow_whatsapp) {
      const whatsapp = create("a", "btn btn-outline");
      whatsapp.href = `https://wa.me/${phone}`;
      whatsapp.target = "_blank"; whatsapp.rel = "noopener noreferrer";
      whatsapp.append(icon("bi-whatsapp"), document.createTextNode("WhatsApp"));
      actions.append(whatsapp);
    }
    if (phone && contact.allow_phone) {
      const call = create("a", "btn btn-outline");
      call.href = `tel:+${phone}`;
      call.append(icon("bi-telephone"), document.createTextNode("Call"));
      actions.append(call);
    }
    if (phone && contact.allow_sms) {
      const sms = create("a", "btn btn-outline");
      sms.href = `sms:+${phone}`;
      sms.append(icon("bi-chat-left-text"), document.createTextNode("SMS"));
      actions.append(sms);
    }
    const email = product.contact_email || contact.email;
    if (typeof email === "string" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      const emailLink = create("a", "btn btn-outline");
      emailLink.href = `mailto:${email}`;
      emailLink.append(icon("bi-envelope"), document.createTextNode("Email"));
      actions.append(emailLink);
    }
    const telegram = product.telegram_username || contact.telegram;
    if (contact.allow_telegram && typeof telegram === "string" && /^[A-Za-z0-9_]{5,32}$/.test(telegram)) {
      const telegramLink = create("a", "btn btn-outline");
      telegramLink.href = `https://t.me/${encodeURIComponent(telegram)}`;
      telegramLink.target = "_blank";
      telegramLink.rel = "noopener noreferrer";
      telegramLink.append(icon("bi-telegram"), document.createTextNode("Telegram"));
      actions.append(telegramLink);
    }
    const favourite = create("button", "btn btn-outline wide");
    favourite.dataset.action = "favorite";
    favourite.dataset.id = product.id;
    favourite.append(icon("bi-heart"), document.createTextNode("Save to favourites"));
    actions.append(favourite);
    info.append(actions);

    const description = create("div", "detail-description");
    description.append(create("h3", "", "A little more about it"), create("p", "", product.description));
    const chips = create("div", "product-meta");
    chips.append(create("span", "tag", product.condition));
    if (product.negotiable) chips.append(create("span", "tag", "Price negotiable"));
    description.append(chips);
    info.append(description);
    const safety = create("div", "alert alert-success");
    safety.textContent = "Meet somewhere safe, inspect the item before agreeing, and never share one-time PINs.";
    info.append(safety);
    layout.append(media, info);
    wrap.append(layout);

    const feedback = create("section", "section-tight");
    feedback.append(sectionHeader("Questions & community notes", "This is community feedback, not proof of a completed transaction."));
    const feedbackGrid = create("div", "settings-grid");
    const notes = create("div", "panel");
    let list;
    if (comments.has(String(product.id))) list = comments.get(String(product.id));
    else list = await window.SokoProducts.listComments(product.id);
    const reviewList = create("div", "reviews-list");
    list.forEach((item, index) => {
      const review = create("article", "review");
      const head = create("div", "review-head");
      const author = typeof item.author === "object" ? item.author.display_name || item.author.first_name : item.author;
      const text = item.text || item.content || "";
      head.append(create("span", "avatar", initials(item.name || author || "Community member")), appendAll(create("div"), [create("strong", "", item.name || author || "Community member"), create("small", "", `${item.date || item.created_at || "Recently"} · ★ ${item.rating || ""}`)]));
      review.append(head, create("p", "", text));
      const helpful = create("button", "btn btn-quiet btn-small");
      helpful.type = "button"; helpful.dataset.action = "helpful"; helpful.dataset.product = product.id;
      helpful.dataset.id = item.id || "";
      helpful.append(icon("bi-hand-thumbs-up"), document.createTextNode("Helpful"));
      const report = create("button", "btn btn-quiet btn-small", "Report");
      report.type = "button"; report.dataset.action = "report-content"; report.dataset.type = "comment"; report.dataset.id = item.id || "";
      review.append(helpful, report);
      reviewList.append(review);
    });
    notes.append(reviewList);
    const askPanel = create("form", "panel");
    askPanel.id = "comment-form";
    askPanel.dataset.product = product.id;
    askPanel.append(create("h3", "", "Ask a question"));
    askPanel.append(create("p", "", "Keep questions about the item. Please be kind and never post private information."));
    const question = create("textarea", "form-control");
    question.name = "comment"; question.required = true; question.maxLength = 1000; question.rows = 4;
    question.placeholder = "What would you like to know?";
    askPanel.append(question);
    const submit = create("button", "btn btn-primary"); submit.type = "submit"; submit.textContent = "Post question";
    askPanel.append(submit);
    feedbackGrid.append(notes, askPanel);
    feedback.append(feedbackGrid);
    wrap.append(feedback);
    main.replaceChildren(wrap);
  }

  function normalKenyanPhone(value) {
    const digits = String(value || "").replace(/\D/g, "");
    if (/^2547\d{8}$/.test(digits)) return digits;
    if (/^07\d{8}$/.test(digits)) return `254${digits.slice(1)}`;
    if (/^7\d{8}$/.test(digits)) return `254${digits}`;
    return "";
  }

  async function renderSeller(name) {
    const seller = await window.SokoProducts.sellerProfile(name);
    if (!seller) {
      renderNotFound("We couldn’t find that seller.", "This seller profile may have moved or been removed.");
      return;
    }
    const sellerId = seller.user_id || seller.id || seller.slug || name;
    const products = await window.SokoProducts.sellerItems(sellerId);
    const reviews = sellerReviews.get(String(sellerId))
      || await window.SokoProducts.sellerReviews(sellerId);
    const sellerName = seller.display_name || seller.name || products[0]?.seller || name || "Local seller";
    const wrap = create("div", "container-wide");
    const hero = create("section", "seller-hero");
    hero.append(create("div", "seller-avatar", initials(sellerName)));
    const profile = create("div");
    profile.append(create("h1", "", sellerName));
    profile.append(create("p", "", seller.bio || "Sharing thoughtful finds and useful things with the neighbourhood."));
    const metrics = create("div", "seller-metrics");
    metrics.append(appendAll(create("span"), [create("strong", "", `${seller.rating || "—"} ★`), document.createTextNode("community rating")]));
    metrics.append(appendAll(create("span"), [create("strong", "", String(products.length)), document.createTextNode("active listings")]));
    metrics.append(appendAll(create("span"), [create("strong", "", seller.joined_at || "SokoMtaani"), document.createTextNode(seller.joined_at ? "joined" : "member")]));
    profile.append(metrics);
    hero.append(profile);
    const contact = create("button", "btn btn-primary");
    contact.type = "button"; contact.dataset.action = "seller-contact";
    contact.dataset.seller = sellerId;
    contact.dataset.sellerName = sellerName;
    contact.append(icon("bi-chat-dots"), document.createTextNode("Message seller"));
    hero.append(contact);
    wrap.append(hero);
    wrap.append(sectionHeader("Listings from this seller", "Take a look at what's available."));
    wrap.append(productGrid(products));
    const reviewPanel = create("section", "panel section-tight");
    reviewPanel.append(create("h2", "", "Seller reviews"), create("p", "", "Community feedback is shared by members; it does not verify a completed transaction."));
    reviews.forEach((review) => reviewPanel.append(create("p", "", `${review.rating || "—"} ★ · ${review.content || review.text || ""}`)));
    const reviewForm = create("form", "review-form");
    reviewForm.id = "seller-review-form";
    reviewForm.dataset.seller = sellerId;
    const rating = create("select", "form-select");
    rating.name = "rating"; rating.required = true;
    [["", "Choose a rating"], ["5", "5 stars"], ["4", "4 stars"], ["3", "3 stars"], ["2", "2 stars"], ["1", "1 star"]]
      .forEach(([value, label]) => rating.append(new Option(label, value)));
    const comment = create("textarea", "form-control");
    comment.name = "content"; comment.required = true; comment.maxLength = 1000; comment.placeholder = "Share constructive feedback.";
    const submit = create("button", "btn btn-outline btn-small"); submit.type = "submit"; submit.textContent = "Leave a review";
    reviewForm.append(rating, comment, submit);
    reviewPanel.append(reviewForm);
    wrap.append(reviewPanel);
    main.replaceChildren(wrap);
  }

  function authShell(title, description, body, eyebrow = "SokoMtaani account") {
    const outer = create("div", "auth-shell");
    const card = create("section", "auth-card");
    card.append(create("span", "eyebrow", eyebrow), create("h1", "", title), create("p", "", description));
    card.append(body);
    outer.append(card);
    return outer;
  }

  function labeledField(labelText, name, type = "text", options = {}) {
    const wrapper = create("div", "form-field");
    const label = create("label", "field-label", labelText);
    label.htmlFor = name;
    const input = create(options.multiline ? "textarea" : "input", "form-control");
    input.id = name;
    input.name = name;
    if (!options.multiline) input.type = type;
    if (options.rows) input.rows = options.rows;
    if (options.placeholder) input.placeholder = options.placeholder;
    if (options.required !== false) input.required = true;
    if (options.maxLength) input.maxLength = options.maxLength;
    if (options.autocomplete) input.autocomplete = options.autocomplete;
    if (!options.multiline && type === "password") {
      const passwordControl = create("div", "password-control");
      passwordControl.append(input);
      const toggle = create("button", "password-toggle", "");
      toggle.type = "button";
      toggle.dataset.action = "toggle-password";
      toggle.setAttribute("aria-label", "Show password");
      toggle.setAttribute("aria-pressed", "false");
      toggle.append(icon("bi-eye"));
      passwordControl.append(toggle);
      wrapper.append(label, passwordControl);
    } else {
      wrapper.append(label, input);
    }
    if (options.hint) wrapper.append(create("small", "form-hint", options.hint));
    return wrapper;
  }

  function formAlert(form, message, success = false) {
    let alert = $(".form-alert", form);
    if (!alert) {
      alert = create("div", "form-alert");
      form.prepend(alert);
    }
    alert.className = `form-alert alert ${success ? "alert-success" : "alert-error"}`;
    alert.textContent = message;
    alert.setAttribute("role", "status");
  }

  async function getSiteInfo() {
    if (siteInfoCache) return siteInfoCache;
    if (!siteInfoRequest) {
      siteInfoRequest = window.SokoDashboard.siteInfo()
        .then((data) => {
          siteInfoCache = data;
          return data;
        })
        .finally(() => { siteInfoRequest = null; });
    }
    return siteInfoRequest;
  }

  function renderLogin(mfa = false) {
    const form = create("form");
    form.id = mfa ? "mfa-form" : "login-form";
    if (mfa) {
      form.append(labeledField("6-digit authenticator code", "code", "text", { autocomplete: "one-time-code", placeholder: "123456", hint: "Use the code from your authenticator app." }));
      const pending = window.SokoAuth.getPendingMfa();
      if (pending?.enrollment_required && pending.provisioning_uri) {
        const enrollment = create("div", "form-field");
        enrollment.append(create("label", "field-label", "Set up your authenticator"));
        enrollment.append(create("p", "", "Scan this setup link with an authenticator app, or copy it into the app manually."));
        const uri = create("code", "mfa-uri", pending.provisioning_uri);
        enrollment.append(uri);
        const copy = create("button", "btn btn-outline btn-small");
        copy.type = "button"; copy.dataset.action = "copy-mfa";
        copy.append(icon("bi-clipboard"), document.createTextNode("Copy setup link"));
        enrollment.append(copy);
        form.append(enrollment);
      }
    } else {
      form.append(labeledField("Email address", "email", "email", { autocomplete: "email", placeholder: "you@example.com" }));
      form.append(labeledField("Password", "password", "password", { autocomplete: "current-password" }));
      const forgot = create("div");
      forgot.style.textAlign = "right";
      const forgotLink = create("a", "text-link", "Forgot password?");
      forgotLink.href = routeHref("/forgot-password");
      forgot.append(forgotLink);
      form.append(forgot);
    }
    const submit = create("button", "btn btn-primary");
    submit.type = "submit"; submit.style.width = "100%"; submit.style.marginTop = "16px";
    submit.append(icon(mfa ? "bi-shield-lock" : "bi-box-arrow-in-right"), document.createTextNode(mfa ? "Verify and continue" : "Log in"));
    form.append(submit);
    const card = authShell(mfa ? "One more step." : "Welcome back.", mfa ? "Enter your authenticator code to continue securely." : "Sign in to pick up where you left off.", form, mfa ? "Account security" : "Good to see you again");
    if (!mfa) {
      const signup = create("p", "form-hint");
      signup.style.textAlign = "center";
      signup.append(document.createTextNode("New to SokoMtaani? "));
      const join = create("a", "text-link", "Create an account"); join.href = routeHref("/register");
      signup.append(join);
      const cardNode = $(".auth-card", card);
      cardNode.append(signup);
    }
    main.replaceChildren(card);
  }

  function renderRegister() {
    const form = create("form");
    form.id = "register-form";
    form.append(labeledField("First name", "first_name", "text", { autocomplete: "given-name" }));
    form.append(labeledField("Last name", "last_name", "text", { autocomplete: "family-name" }));
    form.append(labeledField("Email address", "email", "email", { autocomplete: "email", placeholder: "you@example.com" }));
    const accountMode = create("select", "form-select");
    accountMode.name = "account_mode";
    accountMode.required = true;
    [
      ["general", "Buy and sell"],
      ["buyer", "Buy only"],
      ["seller", "Sell only"],
    ].forEach(([value, label]) => accountMode.append(new Option(label, value)));
    form.append(makeFilterField("How will you use SokoMtaani?", accountMode, "account-mode"));
    form.append(labeledField("Password", "password", "password", { autocomplete: "new-password", hint: "Use at least 8 characters. Choose a password you do not use elsewhere." }));
    const consent = create("label", "form-check");
    const check = create("input"); check.type = "checkbox"; check.name = "terms"; check.required = true;
    consent.append(check);
    const consentText = create("span");
    consentText.append(document.createTextNode("I agree to the "));
    const terms = create("a", "text-link", "Terms"); terms.href = routeHref("/terms");
    consentText.append(terms, document.createTextNode(" and "));
    const privacy = create("a", "text-link", "Privacy Policy"); privacy.href = routeHref("/privacy");
    consentText.append(privacy, document.createTextNode("."));
    consent.append(consentText); form.append(consent);
    const submit = create("button", "btn btn-primary"); submit.type = "submit"; submit.style.width = "100%"; submit.textContent = "Create my account";
    form.append(submit);
    const card = authShell("Join your neighbourhood.", "One account for browsing, saving and selling. You can activate seller features whenever you're ready.", form, "A little closer to home");
    const note = create("div", "alert alert-success");
    note.textContent = "Your account is ready immediately. Seller features require phone verification; email verification is not required.";
    $(".auth-card", card).append(note);
    const login = create("p", "form-hint"); login.style.textAlign = "center";
    login.append(document.createTextNode("Already have an account? "));
    const link = create("a", "text-link", "Log in"); link.href = routeHref("/login"); login.append(link);
    $(".auth-card", card).append(login);
    main.replaceChildren(card);
  }

  function renderForgotPassword() {
    const form = create("form"); form.id = "reset-request-form";
    form.append(labeledField("Email address", "email", "email", { autocomplete: "email" }));
    const submit = create("button", "btn btn-primary"); submit.type = "submit"; submit.style.width = "100%"; submit.textContent = "Send reset instructions";
    form.append(submit);
    main.replaceChildren(authShell("Reset your password.", "If you have an account, we’ll send a link to reset your password.", form, "Account help"));
  }

  function renderResetConfirm(query) {
    const form = create("form"); form.id = "reset-confirm-form";
    form.append(labeledField("New password", "new_password", "password", { autocomplete: "new-password" }));
    const uid = create("input"); uid.type = "hidden"; uid.name = "uid"; uid.value = query.get("uid") || "";
    const token = create("input"); token.type = "hidden"; token.name = "token"; token.value = query.get("token") || "";
    form.append(uid, token);
    const submit = create("button", "btn btn-primary"); submit.type = "submit"; submit.style.width = "100%"; submit.textContent = "Set new password";
    form.append(submit);
    main.replaceChildren(authShell("Choose a new password.", "Create a strong password you haven't used before.", form, "Account security"));
  }

  function renderVerifyEmail(query) {
    const form = create("form"); form.id = "verify-email-form";
    form.append(labeledField("Verification token", "token", "text", { required: true, placeholder: "Paste the token from your email" }));
    if (query.get("token")) $("input[name=token]", form).value = query.get("token");
    const submit = create("button", "btn btn-primary"); submit.type = "submit"; submit.style.width = "100%"; submit.textContent = "Verify my email";
    form.append(submit);
    main.replaceChildren(authShell("Check your inbox.", "Use the secure link in your email, or paste its verification token below.", form, "Email verification"));
  }

  async function renderSellerCreate(productId = null) {
    const existing = productId ? await window.SokoProducts.get(productId) : null;
    const form = create("form", "panel");
    form.id = productId ? "edit-product-form" : "create-product-form";
    if (productId) form.dataset.productId = productId;
    form.append(create("h2", "", "Give your listing a good start"));
    form.append(create("p", "", "Clear details and honest photos help neighbours decide."));
    const fileGroup = create("div", "form-field");
    const fileLabel = create("label", "field-label", "Photos (up to 6)");
    fileLabel.htmlFor = "product-images";
    const files = create("input", "form-control"); files.type = "file"; files.id = "product-images"; files.name = "images"; files.accept = "image/jpeg,image/png,image/webp"; files.multiple = true;
    const preview = create("div", "file-preview"); preview.id = "image-preview";
    fileGroup.append(fileLabel, files, create("small", "form-hint", "JPEG, PNG or WebP. Images are validated by the server before publishing."), preview);
    form.append(fileGroup);
    form.append(labeledField("Listing title", "name", "text", { maxLength: 140, placeholder: "e.g. Teak side table, great condition" }));
    form.append(labeledField("Description", "description", "text", { multiline: true, rows: 5, maxLength: 5000, placeholder: "Share details that help someone picture it in their home." }));
    const row1 = create("div", "form-row");
    const category = create("div", "form-field");
    category.append(create("label", "field-label", "Category"));
    const select = create("select", "form-select"); select.name = "category"; select.required = true;
    const categories = await window.SokoProducts.categories();
    addSelectOptions(select, categories.map((item) => item.name || item.title), "Choose a category");
    select.append(new Option("Request a new category", "__custom__"));
    category.append(select);
    const customCategory = labeledField("New category name", "custom_category", "text", { required: false, maxLength: 100 });
    customCategory.hidden = true;
    select.addEventListener("change", () => { customCategory.hidden = select.value !== "__custom__"; });
    category.append(customCategory);
    const condition = create("div", "form-field");
    condition.append(create("label", "field-label", "Condition"));
    const conditionSelect = create("select", "form-select"); conditionSelect.name = "condition"; conditionSelect.required = true;
    ["New", "Like new", "Gently used"].forEach((item) => conditionSelect.append(new Option(item, item)));
    condition.append(conditionSelect);
    row1.append(category, condition); form.append(row1);
    form.append(labeledField("Price (KES)", "price", "number", { placeholder: "0" }));
    const negotiable = create("label", "form-check");
    const negotiableInput = create("input"); negotiableInput.type = "checkbox"; negotiableInput.name = "negotiable";
    negotiable.append(negotiableInput, create("span", "", "I'm open to reasonable offers"));
    form.append(negotiable);
    const row2 = create("div", "form-row");
    const county = create("div", "form-field");
    county.append(create("label", "field-label", "County"));
    const countySelect = create("select", "form-select"); countySelect.name = "county"; countySelect.required = true;
    addSelectOptions(countySelect, window.SOKO_CONFIG.COUNTIES, "Choose county");
    county.append(countySelect);
    const town = create("div", "form-field");
    town.append(create("label", "field-label", "Town or neighbourhood"));
    const townInput = create("input", "form-control"); townInput.name = "town"; townInput.required = true; townInput.placeholder = "e.g. Kilimani";
    town.append(townInput);
    row2.append(county, town); form.append(row2);
    const previewCard = create("div", "product-preview");
    const previewImage = create("img"); previewImage.alt = "Listing preview"; setMediaSource(previewImage, "");
    const previewText = create("div");
    previewText.append(create("strong", "preview-name", "Your listing title"), create("b", "preview-price", "KES 0"), create("p", "preview-location", "Your location"));
    previewCard.append(previewImage, previewText); form.append(previewCard);
    const actions = create("div"); actions.style.display = "flex"; actions.style.gap = "9px"; actions.style.marginTop = "19px";
    const submit = create("button", "btn btn-primary"); submit.type = "submit"; submit.append(icon("bi-send"), document.createTextNode("Publish listing"));
    if (productId) submit.replaceChildren(icon("bi-check2"), document.createTextNode("Save changes"));
    const cancel = create("a", "btn btn-outline"); cancel.href = routeHref("/seller/listings"); cancel.textContent = "Cancel";
    actions.append(submit, cancel); form.append(actions);
    const page = create("div", "container-wide section-tight");
    const head = create("div", "section-head");
    head.append(appendAll(create("div"), [create("span", "eyebrow", "Seller space"), create("h1", "page-heading", productId ? "Edit your listing" : "List something lovely"), create("p", "", "Your item, your price. People arrange purchases directly with you.")]));
    page.append(head, form);
    if (existing) {
      $('[name="name"]', form).value = existing.name;
      $('[name="description"]', form).value = existing.description;
      $('[name="category"]', form).value = existing.category;
      $('[name="condition"]', form).value = existing.condition;
      $('[name="price"]', form).value = existing.price;
      $('[name="negotiable"]', form).checked = existing.negotiable;
      $('[name="county"]', form).value = existing.county;
      $('[name="town"]', form).value = existing.town;
      $(".preview-name", form).textContent = existing.name;
      $(".preview-price", form).textContent = currency(existing.price);
      $(".preview-location", form).textContent = `${existing.town}, ${existing.county}`;
      setMediaSource($(".product-preview img", form), existing.image);
    }
    return page;
  }

  async function renderDashboard(path, user) {
    const section = path.split("/")[2] || "overview";
    const admin = path.startsWith("/admin");
    if (admin) {
      await renderAdminDashboard(path, user, section);
      return;
    }
    const seller = path.startsWith("/seller");
    const base = admin ? "/admin" : seller ? "/seller" : "/buyer";
    const page = create("div", "container-wide dashboard-layout");
    const side = create("nav", "dashboard-side");
    side.setAttribute("aria-label", "Account navigation");
    side.append(create("div", "side-heading", admin ? "Administration" : seller ? "Seller space" : "Your space"));
    const navItems = seller
        ? [["overview", "Overview", "bi-grid"], ["listings", "My listings", "bi-box-seam"], ["create", "Create listing", "bi-plus-circle"], ["analytics", "Performance", "bi-graph-up"], ["messages", "Messages", "bi-chat-dots"], ["support", "Contact support", "bi-headset"], ["notifications", "Notifications", "bi-bell"], ["profile", "Seller profile", "bi-person-badge"], ["settings", "Account settings", "bi-gear"]]
        : [["overview", "Overview", "bi-grid"], ["favourites", "Favourites", "bi-heart"], ["cart", "Shopping cart", "bi-cart3"], ["messages", "Messages", "bi-chat-dots"], ["support", "Contact support", "bi-headset"], ["notifications", "Notifications", "bi-bell"], ["settings", "Profile & privacy", "bi-gear"], ["blocked", "Blocked users", "bi-slash-circle"]];
    navItems.forEach(([key, label, iconName]) => {
      const link = create("a", key === section ? "selected" : "");
      link.href = routeHref(key === "overview" ? base : `${base}/${key}`);
      link.append(icon(iconName), document.createTextNode(label));
      side.append(link);
    });
    if (!admin && !seller) {
      const activate = create("button", "btn btn-outline btn-small");
      activate.type = "button"; activate.dataset.action = "activate-seller"; activate.style.margin = "10px";
      activate.append(icon("bi-shop"), document.createTextNode("Start selling"));
      side.append(activate);
    }
    page.append(side);
    const content = create("section", "dashboard-content");
    if (seller && section === "create") {
      main.replaceChildren(await renderSellerCreate());
      return;
    }
    if (seller && section === "edit") {
      main.replaceChildren(await renderSellerCreate(path.split("/")[3]));
      return;
    }
    const title = {
      overview: admin ? "Good morning, team." : seller ? `Good morning, ${user.displayName.split(" ")[0]}.` : `Welcome back, ${user.displayName.split(" ")[0]}.`,
      listings: "My listings", favourites: "Your saved finds", messages: "Messages",
      notifications: "Notifications", analytics: "Listing performance", profile: "Seller profile",
      settings: "Account & privacy", blocked: "Blocked users", users: "People on SokoMtaani",
      sellers: "Seller directory", products: "Marketplace listings", categories: "Categories",
      reports: "Reports to review", reviews: "Community feedback", security: "Security activity",
      audit: "Audit log", create: "Create a listing", support: "Support inbox",
      cart: "Your shopping cart", announcements: "Community announcements",
      "category-suggestions": "Category requests",
    }[section] || "Platform analytics";
    const titleBar = create("div", "dashboard-title");
    titleBar.append(create("h1", "", title));
    if (seller && section === "listings") {
      const add = create("a", "btn btn-primary btn-small"); add.href = routeHref("/seller/create");
      add.append(icon("bi-plus-lg"), document.createTextNode("New listing"));
      titleBar.append(add);
    }
    content.append(titleBar);
    if (admin) await renderAdminSection(content, section);
    else if (seller) await renderSellerSection(content, section, user);
    else await renderBuyerSection(content, section, user);
    page.append(content);
    main.replaceChildren(page);
  }

  const ADMIN_SECTION_LABELS = {
    overview: "Overview",
    users: "Users",
    approvals: "Pending approvals",
    sellers: "Sellers",
    products: "Listings",
    orders: "Orders",
    conversations: "Conversations",
    support: "Support inbox",
    announcements: "Announcements",
    notifications: "Notifications",
    categories: "Categories",
    "category-suggestions": "Category requests",
    reports: "Reports",
    reviews: "Reviews",
    messages: "Message reports",
    security: "Security activity",
    audit: "Audit log",
    analytics: "Analytics",
    settings: "Platform settings",
  };

  function adminNavigation(user) {
    if (user.admin_role === "super_admin") {
      return [
        ["Workspace", [["overview", "Overview", "bi-grid-1x2"], ["analytics", "Analytics", "bi-graph-up"]]],
        ["Marketplace", [["users", "Users", "bi-people"], ["sellers", "Sellers", "bi-shop"], ["approvals", "Pending approvals", "bi-person-check"], ["products", "Listings", "bi-box-seam"], ["orders", "Orders", "bi-receipt"], ["conversations", "Conversations", "bi-chat-square-text"], ["support", "Support inbox", "bi-headset"]]],
        ["Community", [["announcements", "Announcements", "bi-megaphone"], ["notifications", "Notifications", "bi-bell"], ["categories", "Categories", "bi-tags"], ["category-suggestions", "Category requests", "bi-tag"]]],
        ["Trust & safety", [["reports", "Reports", "bi-flag"], ["reviews", "Reviews", "bi-star"], ["messages", "Message reports", "bi-chat-left-text"], ["security", "Security activity", "bi-shield-check"], ["audit", "Audit log", "bi-journal-text"]]],
        ["Configuration", [["settings", "Platform settings", "bi-gear"]]],
      ];
    }
    if (user.admin_role === "support_admin") {
      return [
        ["Support", [["users", "Users", "bi-people"], ["sellers", "Sellers", "bi-shop"], ["reports", "Reports", "bi-flag"], ["support", "Support inbox", "bi-headset"]]],
      ];
    }
    return [
      ["Moderation", [["reports", "Reports", "bi-flag"], ["products", "Listings", "bi-box-seam"], ["categories", "Categories", "bi-tags"], ["category-suggestions", "Category requests", "bi-tag"], ["reviews", "Reviews", "bi-star"], ["messages", "Message reports", "bi-chat-left-text"], ["audit", "Audit log", "bi-journal-text"]]],
    ];
  }

  async function renderAdminDashboard(path, user, section) {
    const shell = create("div", "admin-shell");
    const sidebar = create("aside", "admin-sidebar");
    const sidebarBrand = create("div", "admin-sidebar-brand");
    sidebarBrand.append(brandLink());
    const collapse = create("button", "admin-collapse-button");
    collapse.type = "button";
    collapse.dataset.action = "admin-sidebar-toggle";
    collapse.setAttribute("aria-label", "Collapse sidebar");
    collapse.append(icon("bi-layout-sidebar-inset"));
    sidebarBrand.append(collapse);
    sidebar.append(sidebarBrand);

    const nav = create("nav", "admin-navigation");
    nav.setAttribute("aria-label", "Administration");
    adminNavigation(user).forEach(([groupName, links]) => {
      const group = create("div", "admin-nav-group");
      group.append(create("h2", "admin-nav-heading", groupName));
      links.forEach(([key, label, iconName]) => {
        if (key === "orders") {
          const unavailable = create("span", "admin-nav-link is-disabled");
          unavailable.setAttribute("aria-disabled", "true");
          unavailable.title = "Orders are unavailable because the platform has no order records yet.";
          unavailable.append(icon(iconName), create("span", "", label), create("small", "admin-nav-note", "Not tracked"));
          group.append(unavailable);
          return;
        }
        const link = create("a", `admin-nav-link${key === section ? " selected" : ""}`);
        link.href = routeHref(key === "overview" ? "/admin" : `/admin/${key}`);
        link.title = label;
        link.setAttribute("aria-current", key === section ? "page" : "false");
        link.append(icon(iconName), create("span", "", label));
        group.append(link);
      });
      nav.append(group);
    });
    sidebar.append(nav);

    const profile = create("div", "admin-sidebar-profile");
    const avatar = create("span", "admin-avatar", user.initials || initials(user.displayName));
    const identity = create("span", "admin-profile-identity");
    identity.append(create("strong", "", user.displayName || user.email), create("small", "", user.admin_role === "super_admin" ? "Super Admin" : user.admin_role === "moderator" ? "Moderator" : "Support Admin"));
    profile.append(avatar, identity);
    sidebar.append(profile);
    shell.append(sidebar);

    const workspace = create("div", "admin-workspace");
    const toolbar = create("header", "admin-topbar");
    const mobileMenu = create("button", "admin-mobile-menu");
    mobileMenu.type = "button";
    mobileMenu.dataset.action = "admin-sidebar-toggle";
    mobileMenu.setAttribute("aria-label", "Open administration menu");
    mobileMenu.append(icon("bi-list"));
    toolbar.append(mobileMenu);

    const breadcrumb = create("div", "admin-breadcrumb");
    breadcrumb.append(create("span", "", "Workspace"), icon("bi-chevron-right"), create("strong", "", ADMIN_SECTION_LABELS[section] || "Overview"));
    toolbar.append(breadcrumb);

    const search = create("label", "admin-search");
    search.append(icon("bi-search"));
    const searchInput = create("input");
    searchInput.type = "search";
    searchInput.id = "admin-page-search";
    searchInput.placeholder = "Search this page";
    searchInput.setAttribute("aria-label", "Search records on this page");
    search.append(searchInput);
    toolbar.append(search);

    if (["overview", "analytics"].includes(section) && user.admin_role === "super_admin") {
      const periodControl = create("label", "admin-period-control");
      periodControl.append(create("span", "sr-only", "Reporting period"));
      const period = create("select");
      period.id = "admin-period";
      [["7d", "Last 7 days"], ["30d", "Last 30 days"], ["90d", "Last 90 days"], ["12m", "Last 12 months"]]
        .forEach(([value, label]) => period.append(new Option(label, value)));
      period.value = currentRoute?.query.get("period") || "30d";
      periodControl.append(period);
      toolbar.append(periodControl);
    }

    const notifications = await window.SokoDashboard.notifications();
    const unreadCount = notifications.filter((item) => item.unread).length;
    const notificationLink = create("a", "admin-icon-button");
    notificationLink.href = routeHref("/admin/notifications");
    notificationLink.setAttribute("aria-label", `Notifications, ${unreadCount} unread`);
    notificationLink.append(icon("bi-bell"));
    if (unreadCount) notificationLink.append(create("span", "admin-notification-count", String(unreadCount)));
    toolbar.append(notificationLink);

    const systemStatus = create("span", "admin-system-status");
    systemStatus.append(create("i"), document.createTextNode("API connected"));
    toolbar.append(systemStatus);
    const profileMenu = create("div", "admin-profile-menu");
    const profileButton = create("button", "admin-profile-button");
    profileButton.type = "button";
    profileButton.dataset.action = "admin-profile-menu";
    profileButton.setAttribute("aria-expanded", "false");
    profileButton.append(
      create("span", "admin-avatar admin-avatar-small", user.initials || initials(user.displayName)),
      create("span", "", user.displayName || user.email),
      icon("bi-chevron-down"),
    );
    const dropdown = create("div", "admin-profile-dropdown");
    dropdown.hidden = true;
    dropdown.append(create("small", "", user.admin_role === "super_admin" ? "Super Admin" : user.admin_role === "moderator" ? "Moderator" : "Support Admin"));
    const signOut = create("button", "", "Sign out");
    signOut.type = "button";
    signOut.dataset.action = "logout";
    dropdown.append(signOut);
    profileMenu.append(profileButton, dropdown);
    toolbar.append(profileMenu);
    workspace.append(toolbar);

    const content = create("main", "admin-page-content");
    if (section === "overview" || section === "analytics") {
      const period = currentRoute?.query.get("period") || "30d";
      const data = await window.SokoDashboard.adminAnalytics(period);
      renderExecutiveDashboard(content, data, user, section);
    } else if (section === "orders") {
      const heading = create("div", "admin-page-heading");
      heading.append(create("span", "admin-eyebrow", "Marketplace operations"), create("h1", "", "Orders"), create("p", "", "Order management will appear here when the marketplace has an order and payment workflow."));
      const unavailable = create("section", "admin-unavailable-panel");
      unavailable.append(icon("bi-receipt"), create("h2", "", "Order data is not available"), create("p", "", "SokoMtaani currently connects buyers and sellers directly. It does not record orders, payments, or revenue."));
      content.append(heading, unavailable);
    } else {
      const heading = create("div", "admin-page-heading");
      const descriptions = {
        users: "Manage member access and account records.",
        sellers: "Review seller profiles and activation status.",
        approvals: "Review legacy accounts awaiting approval.",
        products: "Moderate marketplace listings.",
        conversations: "Review conversation metadata without exposing private message contents.",
        support: "Respond to member requests in the dedicated support inbox.",
        announcements: "Publish updates for the marketplace community.",
        notifications: "Review administrative alerts and updates.",
        categories: "Manage the marketplace taxonomy.",
        "category-suggestions": "Review member requests for new categories.",
        reports: "Investigate reports and take proportionate action.",
        reviews: "Review seller feedback and visibility.",
        messages: "Access private message evidence only when assigned to a report.",
        security: "Review account security events and access activity.",
        audit: "Review recorded administrative actions.",
        settings: "Manage platform contact and community information.",
      };
      const moderatorHome = user.admin_role === "moderator" && section === "reports";
      heading.append(
        create("span", "admin-eyebrow", moderatorHome ? "Trust & safety" : "Administration"),
        create("h1", "", moderatorHome ? "Moderation command center" : ADMIN_SECTION_LABELS[section] || "Administration"),
        create("p", "", moderatorHome ? "Prioritize reports, investigate content and review recent account actions." : descriptions[section] || "Manage marketplace operations."),
      );
      content.append(heading);
      if (moderatorHome) {
        const stats = await window.SokoDashboard.admin("moderation-analytics");
        const metrics = create("div", "admin-kpi-grid admin-moderation-metrics");
        metrics.append(
          adminMetric("bi-inbox", "Pending reports", Number(stats.pending_reports || 0).toLocaleString(), "Open and assigned", "blue"),
          adminMetric("bi-person-exclamation", "Reported accounts", Number(stats.reported_accounts || 0).toLocaleString(), "Awaiting investigation", "amber"),
          adminMetric("bi-card-image", "Reported listings", Number(stats.reported_listings || 0).toLocaleString(), "Open listing reports", "cyan"),
          adminMetric("bi-shield-check", "Resolved reports", Number(stats.resolved_reports || 0).toLocaleString(), `${Number(stats.recent_suspensions || 0)} suspensions in the last 7 days`, "violet"),
        );
        content.append(metrics);
      }
      await renderAdminSection(content, section);
    }
    workspace.append(content);
    shell.append(workspace);
    main.replaceChildren(shell);
  }

  function adminMetric(iconName, label, value, detail, accent) {
    const card = create("article", `admin-kpi admin-kpi-${accent}`);
    const top = create("div", "admin-kpi-top");
    const iconWrap = create("span", "admin-kpi-icon");
    iconWrap.append(icon(iconName));
    top.append(iconWrap, create("span", "admin-kpi-label", label));
    card.append(top, create("strong", "admin-kpi-value", String(value)), create("small", "admin-kpi-detail", detail));
    return card;
  }

  function adminPanelHeading(title, description) {
    const heading = create("div", "admin-panel-heading");
    const copy = create("div");
    copy.append(create("h2", "", title), create("p", "", description));
    heading.append(copy);
    return heading;
  }

  function svgNode(name, attributes = {}) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
  }

  function renderGrowthChart(data) {
    const labels = data.trend_labels || [];
    const users = data.user_growth || [];
    const listings = data.listing_growth || [];
    const width = 820;
    const height = 276;
    const inset = { top: 20, right: 18, bottom: 42, left: 44 };
    const plotWidth = width - inset.left - inset.right;
    const plotHeight = height - inset.top - inset.bottom;
    const maximum = Math.max(1, ...users, ...listings);
    const chart = svgNode("svg", {
      viewBox: `0 0 ${width} ${height}`,
      role: "img",
      "aria-label": "New user registrations and new listings over the selected reporting period",
    });
    const definitions = svgNode("defs");
    const userGradient = svgNode("linearGradient", { id: "adminUserGradient", x1: "0", x2: "0", y1: "0", y2: "1" });
    userGradient.append(svgNode("stop", { offset: "0%", "stop-color": "#3b82f6", "stop-opacity": ".58" }));
    userGradient.append(svgNode("stop", { offset: "100%", "stop-color": "#3b82f6", "stop-opacity": "0" }));
    const listingGradient = svgNode("linearGradient", { id: "adminListingGradient", x1: "0", x2: "0", y1: "0", y2: "1" });
    listingGradient.append(svgNode("stop", { offset: "0%", "stop-color": "#06b6d4", "stop-opacity": ".48" }));
    listingGradient.append(svgNode("stop", { offset: "100%", "stop-color": "#06b6d4", "stop-opacity": "0" }));
    definitions.append(userGradient, listingGradient);
    chart.append(definitions);
    for (let index = 0; index < 4; index += 1) {
      const y = inset.top + (plotHeight * index) / 3;
      chart.append(svgNode("line", { x1: inset.left, y1: y, x2: width - inset.right, y2: y, class: "admin-chart-grid" }));
      const value = Math.round(maximum * (1 - index / 3));
      const label = svgNode("text", { x: inset.left - 10, y: y + 4, "text-anchor": "end", class: "admin-chart-axis" });
      label.textContent = String(value);
      chart.append(label);
    }
    const pathFor = (values) => values.map((value, index) => {
      const x = inset.left + (values.length < 2 ? plotWidth / 2 : (plotWidth * index) / (values.length - 1));
      const y = inset.top + plotHeight * (1 - value / maximum);
      return `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    [
      [users, "admin-chart-line-users", "admin-chart-area-users"],
      [listings, "admin-chart-line-listings", "admin-chart-area-listings"],
    ].forEach(([values, lineClass, areaClass]) => {
      if (!values.length) return;
      const linePath = pathFor(values);
      const areaPath = `${linePath} L${width - inset.right},${height - inset.bottom} L${inset.left},${height - inset.bottom} Z`;
      chart.append(svgNode("path", { d: areaPath, class: areaClass }));
      chart.append(svgNode("path", { d: linePath, class: lineClass }));
    });
    const visibleLabels = labels.length <= 8
      ? labels.map((_, index) => index)
      : [0, Math.round((labels.length - 1) / 4), Math.round((labels.length - 1) / 2), Math.round((3 * (labels.length - 1)) / 4), labels.length - 1];
    visibleLabels.forEach((index) => {
      const x = inset.left + (labels.length < 2 ? plotWidth / 2 : (plotWidth * index) / (labels.length - 1));
      const label = svgNode("text", { x, y: height - 12, "text-anchor": "middle", class: "admin-chart-axis" });
      label.textContent = labels[index] || "";
      chart.append(label);
    });
    return chart;
  }

  function renderCategoryDistribution(data) {
    const panel = create("section", "admin-panel admin-category-panel");
    const rows = data.category_distribution || [];
    const total = rows.reduce((sum, item) => sum + item.count, 0);
    panel.append(adminPanelHeading("Category mix", "Share of currently active listings"));
    if (!total) {
      panel.append(create("div", "admin-chart-empty", "No active listing data is available yet."));
      return panel;
    }
    const colors = ["#3b82f6", "#22d3ee", "#10b981", "#f59e0b", "#a78bfa", "#fb7185"];
    let offset = 0;
    const segments = rows.map((item, index) => {
      const share = (item.count / total) * 100;
      const segment = `${colors[index % colors.length]} ${offset}% ${offset + share}%`;
      offset += share;
      return segment;
    });
    const chartRow = create("div", "admin-donut-layout");
    const donut = create("div", "admin-donut");
    donut.style.background = `conic-gradient(${segments.join(", ")})`;
    const center = create("div", "admin-donut-center");
    center.append(create("strong", "", String(total)), create("small", "", "listings"));
    donut.append(center);
    const legend = create("div", "admin-chart-legend");
    rows.forEach((item, index) => {
      const row = create("div", "admin-legend-row");
      const marker = create("i");
      marker.style.backgroundColor = colors[index % colors.length];
      row.append(marker, create("span", "", item["category__name"]), create("strong", "", String(item.count)));
      legend.append(row);
    });
    chartRow.append(donut, legend);
    panel.append(chartRow);
    return panel;
  }

  const COUNTY_MAP_POINTS = {
    Turkana: [129, 40],
    Marsabit: [187, 48],
    Mandera: [232, 58],
    Wajir: [219, 100],
    Garissa: [223, 145],
    Isiolo: [191, 111],
    Samburu: [159, 92],
    "West Pokot": [118, 100],
    TransNzoia: [115, 131],
    UasinGishu: [139, 131],
    Kisumu: [102, 151],
    Nakuru: [153, 145],
    Nairobi: [177, 174],
    Mombasa: [226, 231],
    Kilifi: [230, 207],
    Nyeri: [179, 150],
    Meru: [194, 131],
    Kakamega: [98, 132],
    "Narok": [139, 180],
    "Taita-Taveta": [199, 205],
  };

  function renderCountyDistribution(data) {
    const panel = create("section", "admin-panel admin-map-panel");
    const rows = data.county_distribution || [];
    panel.append(adminPanelHeading("Marketplace by county", "Active listings by location · schematic map"));
    if (!rows.length) {
      panel.append(create("div", "admin-chart-empty", "County-level listing data will appear when listings are published."));
      return panel;
    }
    const layout = create("div", "admin-map-layout");
    const mapWrap = create("div", "admin-kenya-map");
    const map = svgNode("svg", { viewBox: "0 0 300 270", role: "img", "aria-label": "Schematic map of Kenya with active listing counts by county" });
    map.append(svgNode("path", {
      class: "admin-kenya-outline",
      d: "M82 21 L112 13 L140 20 L158 15 L177 26 L193 27 L208 41 L224 47 L235 62 L231 79 L245 91 L240 108 L251 121 L239 137 L240 153 L231 171 L232 188 L221 204 L214 221 L199 231 L183 223 L168 215 L155 204 L140 193 L128 179 L116 169 L103 153 L91 139 L81 123 L69 108 L64 91 L70 74 L61 60 L69 47 L64 35 Z",
    }));
    const maximum = Math.max(1, ...rows.map((item) => item.count));
    rows.forEach((item) => {
      const point = COUNTY_MAP_POINTS[item.county];
      if (!point) return;
      const radius = 4 + (item.count / maximum) * 7;
      const marker = svgNode("circle", { cx: point[0], cy: point[1], r: radius, class: "admin-map-marker" });
      const title = svgNode("title");
      title.textContent = `${item.county}: ${item.count} active listings`;
      marker.append(title);
      map.append(marker);
    });
    mapWrap.append(map, create("small", "", "Markers show counties with available active listings."));
    const stats = create("div", "admin-county-list");
    rows.slice(0, 6).forEach((item, index) => {
      const row = create("div", "admin-county-row");
      row.append(create("span", "admin-county-rank", String(index + 1).padStart(2, "0")), create("strong", "", item.county), create("b", "", String(item.count)));
      stats.append(row);
    });
    layout.append(mapWrap, stats);
    panel.append(layout);
    return panel;
  }

  function renderActivityFeed(data) {
    const panel = create("section", "admin-panel");
    panel.append(adminPanelHeading("Recent recorded activity", "Security and administrative events recorded by the platform"));
    const events = data.recent_activity || [];
    if (!events.length) {
      panel.append(create("div", "admin-chart-empty", "No recent audit events have been recorded."));
      return panel;
    }
    const list = create("div", "admin-activity-list");
    events.forEach((event) => {
      const action = String(event.action || "");
      const iconName = action.includes("report") ? "bi-flag" : action.includes("product") ? "bi-box-seam" : action.includes("user") || action.includes("account") ? "bi-person" : "bi-shield-check";
      const row = create("div", "admin-activity-item");
      const badge = create("span", "admin-activity-icon");
      badge.append(icon(iconName));
      row.append(badge);
      const detail = create("div");
      detail.append(create("strong", "", action.replaceAll(".", " ")), create("small", "", `${event.actor} · ${event.target_type}`));
      const timestamp = new Date(event.created_at);
      row.append(detail, create("time", "", Number.isNaN(timestamp.getTime()) ? "" : timestamp.toLocaleString("en-KE", { dateStyle: "medium", timeStyle: "short" })));
      list.append(row);
    });
    panel.append(list);
    return panel;
  }

  function renderUnavailableOrdersPanel() {
    const panel = create("section", "admin-panel admin-orders-panel");
    panel.append(adminPanelHeading("Recent orders", "Order references, payment states and revenue are not recorded yet"));
    const empty = create("div", "admin-orders-empty");
    const badge = create("span", "admin-orders-icon");
    badge.append(icon("bi-receipt"));
    empty.append(badge, create("strong", "", "Order workflow not configured"));
    empty.append(create("p", "", "The marketplace currently connects buyers and sellers directly. No order or payment model exists, so order totals and revenue are intentionally not shown."));
    panel.append(empty);
    return panel;
  }

  function renderExecutiveDashboard(content, data, user, section) {
    const firstName = user.first_name || user.displayName?.split(" ")[0] || "Administrator";
    const hour = new Date().getHours();
    const salutation = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
    const hero = create("section", "admin-welcome-banner");
    const welcome = create("div");
    welcome.append(create("span", "admin-eyebrow", "SokoMtaani · Marketplace operations"), create("h1", "", `${salutation}, ${firstName}`), create("p", "", "Here’s what’s happening across your marketplace today."));
    const date = create("span", "admin-banner-date");
    date.append(icon("bi-calendar3"), document.createTextNode(new Intl.DateTimeFormat("en-KE", { dateStyle: "medium" }).format(new Date())));
    hero.append(welcome, date, create("div", "admin-cityscape"));
    content.append(hero);

    const metrics = create("div", "admin-kpi-grid");
    metrics.append(
      adminMetric("bi-receipt", "Total orders", "Not tracked", "No order records available", "blue"),
      adminMetric("bi-people", "Total users", Number(data.users || 0).toLocaleString(), `${Number(data.active_users || 0).toLocaleString()} active accounts`, "cyan"),
      adminMetric("bi-shop", "Active sellers", Number(data.active_sellers || 0).toLocaleString(), "Verified seller profiles", "violet"),
      adminMetric("bi-cash-stack", "Total revenue", "Not tracked", "No payment records available", "amber"),
    );
    content.append(metrics);

    const secondary = create("div", "admin-secondary-metrics");
    [
      ["Active listings", data.active_products],
      ["Pending approvals", data.pending_approvals],
      ["Open reports", data.open_reports],
      ["Open support", data.support_conversations],
    ].forEach(([label, value]) => {
      const metric = create("div", "admin-secondary-metric");
      metric.append(create("span", "", label), create("strong", "", Number(value || 0).toLocaleString()));
      secondary.append(metric);
    });
    content.append(secondary);

    const trendPanel = create("section", "admin-panel admin-trend-panel");
    const trendHeading = create("div", "admin-panel-heading");
    const trendCopy = create("div");
    trendCopy.append(
      create("h2", "", section === "analytics" ? "Marketplace analytics" : "Marketplace growth"),
      create("p", "", "New accounts and listings created during the selected period"),
    );
    trendHeading.append(trendCopy);
    const legend = create("div", "admin-trend-legend");
    legend.append(create("span", "users", "New users"), create("span", "listings", "New listings"));
    trendHeading.append(legend);
    trendPanel.append(trendHeading, renderGrowthChart(data));
    content.append(trendPanel);

    const discovery = create("div", "admin-insight-grid");
    discovery.append(renderCountyDistribution(data), renderCategoryDistribution(data));
    content.append(discovery);

    const operations = create("div", "admin-operations-grid");
    operations.append(renderUnavailableOrdersPanel(), renderActivityFeed(data));
    content.append(operations);
  }

  async function renderBuyerSection(content, section, user) {
    if (section === "overview") {
      const stats = create("div", "metric-grid");
      const [saved, conversations, notifications] = await Promise.all([
        window.SokoProducts.favorites(), window.SokoMessages.list(), window.SokoDashboard.notifications(),
      ]);
      const unread = notifications.filter((item) => item.unread || item.is_read === false).length;
      [["bi-heart", saved.length, "Saved finds"], ["bi-chat-dots", conversations.length, "Active conversations"], ["bi-bell", unread, "New updates"], ["bi-shield-check", "Anytime", "Browse safely"]].forEach(([ic, value, label]) => stats.append(metricCard(ic, value, label)));
      content.append(stats);
      content.append(sectionHeader("Saved for a little later", "Your favourites are waiting when you are.", "/buyer/favourites"));
      content.append(productGrid(saved.slice(0, 4), true));
      if (!saved.length) {
        const note = create("p", "form-hint", "Tap the heart on a listing to save it here.");
        content.append(note);
      }
      return;
    }
    if (section === "favourites") {
      const saved = await window.SokoProducts.favorites();
      content.append(productGrid(saved));
      return;
    }
    if (section === "cart") {
      const items = await window.SokoDashboard.cart();
      if (!items.length) {
        content.append(create("div", "empty-state", "Your cart is empty."));
        return;
      }
      items.forEach((item) => {
        const row = create("div", "listing-row");
        row.append(create("strong", "", item.product?.name || "Listing"));
        row.append(create("span", "", `KES ${Number(item.product?.price || 0).toLocaleString()}`));
        const remove = create("button", "btn btn-outline btn-small", "Remove");
        remove.type = "button";
        remove.dataset.action = "remove-cart-item";
        remove.dataset.id = item.product?.id;
        row.append(remove);
        content.append(row);
      });
      return;
    }
    if (section === "messages") { await renderMessages(content); return; }
    if (section === "support") { await renderSupport(content, false); return; }
    if (section === "notifications") { await renderNotifications(content); return; }
    if (section === "settings") { await renderSettings(content, "buyer"); return; }
    if (section === "blocked") {
      const users = await window.SokoMessages.blockedUsers();
      if (!users.length) {
        const empty = create("div", "empty-state"); empty.append(icon("bi-slash-circle"), create("h3", "", "Your blocked list is clear"), create("p", "", "People you block will show up here."));
        content.append(empty);
      } else users.forEach((user) => {
        const id = typeof user === "object" ? user.id : user;
        const label = typeof user === "object" ? user.display_name || user.name || user.email || id : user;
        const row = create("div", "listing-row");
        row.append(create("span", "avatar", initials(label)));
        row.append(create("strong", "", label));
        const unblock = create("button", "btn btn-outline btn-small", "Unblock");
        unblock.type = "button"; unblock.dataset.action = "unblock-user"; unblock.dataset.id = id;
        row.append(unblock); content.append(row);
      });
      return;
    }
    renderNotFoundInto(content, "This buyer page is not available.");
  }

  async function renderSupport(content, isAdmin) {
    const conversations = await window.SokoDashboard.supportConversations();
    if (!isAdmin) {
      const form = create("form", "panel");
      form.id = "support-compose-form";
      form.append(create("h2", "", "Contact SokoMtaani support"));
      form.append(labeledField("Subject", "subject", "text", { maxLength: 180 }));
      form.append(labeledField("Message", "message", "text", { multiline: true, rows: 4, maxLength: 4000 }));
      const send = create("button", "btn btn-primary", "Send message");
      send.type = "submit";
      form.append(send);
      content.append(form);
    }
    conversations.forEach((conversation) => {
      const panel = create("article", "panel");
      panel.append(create("h2", "", conversation.subject));
      if (isAdmin) panel.append(create("p", "form-hint", conversation.user_email || ""));
      (conversation.messages || []).forEach((message) => {
        const row = create("div", "support-message");
        row.append(create("strong", "", message.sender_name || "Member"), create("p", "", message.body));
        row.append(create("small", "", message.created_at || ""));
        panel.append(row);
      });
      const reply = create("form", "support-reply-form");
      reply.dataset.id = conversation.id;
      reply.append(labeledField("Reply", "body", "text", { multiline: true, rows: 2, maxLength: 4000 }));
      const send = create("button", "btn btn-outline btn-small", "Send reply");
      send.type = "submit";
      reply.append(send);
      panel.append(reply);
      content.append(panel);
    });
    if (!conversations.length && isAdmin) content.append(create("p", "empty-state", "No support conversations yet."));
  }

  async function renderSellerSection(content, section, user) {
    if (section === "overview") {
      const data = await window.SokoDashboard.overview();
      const stats = create("div", "metric-grid");
      [
        ["bi-box-seam", data.activeListings, "Active listings"],
        ["bi-eye", Number(data.views).toLocaleString(), "Listing views"],
        ["bi-chat-dots", data.enquiries, "Enquiries"],
        ["bi-heart", data.favourites, "Favourites"],
      ].forEach(([ic, value, label], index) => {
        const card = metricCard(ic, value, label);
        if (index === 1) card.querySelector(".metric-card span").append(document.createTextNode(` · ${data.change}`));
        stats.append(card);
      });
      content.append(stats);
      const grid = create("div", "dashboard-grid");
      const performance = create("div", "panel");
      performance.append(create("h3", "", "Your listings are finding people"), create("p", "", "Views over the last 12 weeks"));
      const bars = create("div", "chart-bars");
      data.monthly.forEach((value) => {
        const bar = create("div", "chart-bar"); bar.style.height = `${Math.max(12, value / 80 * 100)}%`; bar.title = `${value} views`; bars.append(bar);
      });
      performance.append(bars);
      const labels = create("div", "chart-labels");
      data.monthlyLabels.forEach((label) => labels.append(create("span", "", label)));
      performance.append(labels);
      grid.append(performance);
      if (data.recentActivity.length) {
        const activity = create("div", "panel");
        activity.append(create("h3", "", "A little activity"), create("p", "", "Recent moments in your shop."));
        const activities = create("div", "activity-list");
        const activityItems = data.recentActivity.map((item) => [item.icon || "bi-activity", item.title || item.description || "Marketplace activity", item.time || item.created_at || "Recently"]);
        activityItems.forEach(([ic, titleText, time]) => activities.append(activityRow(ic, titleText, time)));
        activity.append(activities); grid.append(activity);
      }
      content.append(grid);
      if (data.topListing) {
        const top = create("section", "section-tight");
        top.append(sectionHeader("A listing to check in on", "Keep availability and details up to date."));
        top.append(listingRow(data.topListing));
        content.append(top);
      }
      return;
    }
    if (section === "listings") {
      const userListings = await window.SokoDashboard.listings();
      if (!userListings.length) {
        const empty = create("div", "empty-state");
        empty.append(icon("bi-box-seam"), create("h3", "", "Your shop is ready for its first listing"), create("p", "", "Add a clear photo and a few useful details to get started."));
        const createLink = create("a", "btn btn-primary"); createLink.href = routeHref("/seller/create"); createLink.textContent = "Create a listing";
        empty.append(createLink); content.append(empty);
      } else userListings.forEach((product) => content.append(listingRow(product)));
      return;
    }
    if (section === "analytics") {
      const data = await window.SokoDashboard.overview();
      const metrics = create("div", "metric-grid");
      [["bi-eye", data.views, "Product views"], ["bi-person-check", data.uniqueVisitors, "Unique visitors"], ["bi-chat-dots", data.enquiries, "Product enquiries"], ["bi-heart", data.favourites, "Favourites"]].forEach(([ic, value, label]) => metrics.append(metricCard(ic, value, label)));
      content.append(metrics);
      content.append(create("div", "panel", "Listing performance"));
      const products = await window.SokoDashboard.listings();
      products.slice(0, 4).forEach((product) => content.append(listingRow(product)));
      return;
    }
    if (section === "messages") { await renderMessages(content); return; }
    if (section === "support") { await renderSupport(content, false); return; }
    if (section === "notifications") { await renderNotifications(content); return; }
    if (section === "profile") { await renderSettings(content, "seller", user); return; }
    if (section === "settings") { await renderSettings(content, "buyer", user); return; }
    renderNotFoundInto(content, "This seller page is not available.");
  }

  function metricCard(iconName, value, label) {
    const card = create("div", "metric-card");
    const badge = create("span", "metric-icon"); badge.append(icon(iconName));
    card.append(badge, create("strong", "", String(value)), create("span", "", label));
    return card;
  }

  function activityRow(iconName, title, time) {
    const row = create("div", "activity");
    const badge = create("span", "activity-icon"); badge.append(icon(iconName));
    const text = create("div"); text.append(create("strong", "", title), create("small", "", time));
    row.append(badge, text);
    return row;
  }

  function listingRow(product) {
    const row = create("div", "listing-row");
    const img = create("img"); setMediaSource(img, product.image); img.alt = "";
    const info = create("div"); info.append(create("strong", "", product.name), create("small", "", `${currency(product.price)} · ${product.views} views · ${product.status || "active"}`));
    const actions = create("div", "listing-actions");
    const view = create("a", "icon-btn"); view.href = routeHref(`/product/${product.id}`); view.setAttribute("aria-label", "View listing"); view.append(icon("bi-box-arrow-up-right"));
    const edit = create("a", "icon-btn"); edit.href = routeHref(`/seller/edit/${product.id}`); edit.setAttribute("aria-label", "Edit listing"); edit.append(icon("bi-pencil"));
    const availability = create("button", "icon-btn");
    availability.type = "button";
    availability.dataset.action = "listing-action";
    availability.dataset.id = product.id;
    availability.dataset.status = product.status === "active" ? "paused" : "active";
    availability.setAttribute("aria-label", product.status === "active" ? "Pause listing" : "Activate listing");
    availability.append(icon(product.status === "active" ? "bi-pause-circle" : "bi-play-circle"));
    actions.append(view, edit, availability);
    row.append(img, info, actions);
    return row;
  }

  async function renderMessages(content) {
    const shell = create("div", "message-layout");
    const list = await window.SokoMessages.list();
    const conversationList = create("section", "conversation-list");
    conversationList.append(create("h2", "", "Messages"));
    list.forEach((conversation) => {
      const button = create("button", `conversation-item${conversation.id === activeConversation ? " selected" : ""}`);
      button.type = "button"; button.dataset.action = "select-conversation"; button.dataset.id = conversation.id;
      button.append(create("span", "avatar", conversation.initials || initials(conversation.other_user?.display_name || conversation.recipient?.display_name || "Member")));
      const body = create("span", "conv-body");
      body.append(create("strong", "", conversation.person || conversation.other_user?.display_name || conversation.recipient?.display_name || "Conversation"), create("small", "", conversation.last || conversation.last_message?.content || ""));
      button.append(body, create("span", "conv-time", conversation.time));
      conversationList.append(button);
    });
    shell.append(conversationList);
    const pane = create("section", "message-pane");
    const conversation = await window.SokoMessages.get(activeConversation);
    if (!conversation) {
      pane.append(create("div", "empty-state", "Choose a conversation to get started."));
      shell.append(pane); content.append(shell); return;
    }
    const head = create("div", "message-head");
    const person = create("div"); person.append(create("strong", "", conversation.person || conversation.other_user?.display_name || "Conversation"), create("small", "", "Usually replies in a few hours"));
    const headActions = create("div");
    const back = create("button", "icon-btn mobile-back"); back.type = "button"; back.dataset.action = "message-back"; back.append(icon("bi-arrow-left"));
    const report = create("button", "icon-btn"); report.type = "button"; report.dataset.action = "report-conversation"; report.dataset.userId = conversation.other_user_id || conversation.other_user?.id || conversation.recipient?.id || ""; report.title = "Report member"; report.append(icon("bi-flag"));
    const block = create("button", "icon-btn"); block.type = "button"; block.dataset.action = "block-conversation"; block.dataset.userId = conversation.other_user_id || conversation.other_user?.id || conversation.recipient?.id || ""; block.title = "Block this member"; block.append(icon("bi-slash-circle"));
    headActions.append(back, report, block);
    head.append(person, headActions);
    pane.append(head);
    const linked = create("div", "linked-product");
    if (conversation.product || conversation.product_detail) {
      linked.append(document.createTextNode("About: "));
      const productName = conversation.product_detail?.name || conversation.product?.name || "Marketplace listing";
      const productId = conversation.product_detail?.id || conversation.product?.id || conversation.product;
      const productLink = create("a", "", productName); productLink.href = routeHref(`/product/${productId}`);
      linked.append(productLink);
    } else linked.textContent = "Marketplace conversation";
    pane.append(linked);
    const messages = create("div", "message-list");
    (conversation.messages || conversation.message_set || []).forEach((message) => {
      const bubble = create("div", `message-bubble${message.mine ? " mine" : ""}`);
      bubble.append(document.createTextNode(message.text || message.content || ""), create("small", "", message.time || message.created_at || ""));
      if (message.attachment) {
        const attachment = create("img");
        setMediaSource(attachment, message.attachment);
        attachment.alt = "Shared image";
        attachment.style.maxWidth = "200px";
        attachment.style.borderRadius = "8px";
        bubble.prepend(attachment);
      }
      messages.append(bubble);
    });
    pane.append(messages);
    const compose = create("form", "message-compose"); compose.id = "message-compose"; compose.dataset.id = conversation.id;
    const attachment = create("label", "icon-btn"); attachment.title = "Attach image";
    attachment.append(icon("bi-paperclip"));
    const file = create("input"); file.type = "file"; file.accept = "image/jpeg,image/png,image/webp"; file.hidden = true; file.name = "attachment";
    attachment.append(file);
    const attachmentStatus = create("small", "form-hint"); attachmentStatus.id = "attachment-status";
    const textarea = create("textarea", "form-control"); textarea.name = "message"; textarea.required = true; textarea.maxLength = 2000; textarea.rows = 1; textarea.placeholder = "Write a message...";
    const send = create("button", "btn btn-primary"); send.type = "submit"; send.setAttribute("aria-label", "Send message"); send.append(icon("bi-send"));
    compose.append(attachment, textarea, attachmentStatus, send);
    pane.append(compose);
    shell.append(pane);
    if (window.matchMedia("(max-width: 760px)").matches) shell.classList.add("show-conversation");
    content.append(shell);
    messages.scrollTop = messages.scrollHeight;
  }

  async function renderNotifications(content) {
    const notifications = await window.SokoDashboard.notifications();
    const panel = create("div", "panel");
    notifications.forEach((item) => {
      const row = create("div", `notification-item${item.unread ? " unread" : ""}`);
      const badge = create("span", "activity-icon"); badge.append(icon(item.icon));
      const text = create("div"); text.append(create("strong", "", item.title), create("p", "", item.text), create("small", "", item.time));
      if (item.unread) {
        const mark = create("button", "btn btn-quiet btn-small", "Mark as read");
        mark.type = "button";
        mark.dataset.action = "mark-notification";
        mark.dataset.id = item.id || "";
        text.append(mark);
      }
      const remove = create("button", "btn btn-quiet btn-small", "Delete");
      remove.type = "button";
      remove.dataset.action = "delete-notification";
      remove.dataset.id = item.id || "";
      text.append(remove);
      row.append(badge, text);
      panel.append(row);
    });
    content.append(panel);
  }

  async function renderSettings(content, mode, user) {
    const [preferences, profileData] = await Promise.all([
      window.SokoDashboard.getPreferences(),
      window.SokoDashboard.getProfile(mode === "seller"),
    ]);
    savedPrivacy.email = preferences.email ?? preferences.email_notifications ?? true;
    savedPrivacy.messages = preferences.messages ?? preferences.message_notifications ?? true;
    savedPrivacy.priceChanges = preferences.price_changes ?? preferences.priceChanges ?? true;
    const grid = create("div", "settings-grid");
    const profile = create("form", "setting-card"); profile.id = "profile-form";
    profile.dataset.seller = String(mode === "seller");
    profile.append(create("h3", "", mode === "seller" ? "Seller profile" : "Your details"));
    if (mode === "seller") {
      profile.append(labeledField("Display name", "display_name", "text", { placeholder: "How neighbours see you" }));
    } else {
      profile.append(labeledField("First name", "first_name", "text", { autocomplete: "given-name" }));
      profile.append(labeledField("Last name", "last_name", "text", { autocomplete: "family-name" }));
    }
    profile.append(labeledField("County", "county", "text", { placeholder: "e.g. Nairobi" }));
    if (mode === "seller") profile.append(labeledField("Town", "town", "text", { placeholder: "e.g. Nakuru" }));
    profile.append(labeledField("A little about you", "bio", "text", { multiline: true, rows: 3, placeholder: "Share a little introduction." }));
    if (mode === "seller") $('[name="display_name"]', profile).value = profileData.display_name || "";
    else {
      $('[name="first_name"]', profile).value = profileData.first_name || user?.first_name || "";
      $('[name="last_name"]', profile).value = profileData.last_name || user?.last_name || "";
    }
    $('[name="county"]', profile).value = profileData.county || "";
    if (mode === "seller") $('[name="town"]', profile).value = profileData.town || "";
    $('[name="bio"]', profile).value = profileData.bio || "";
    if (mode === "seller") {
      const contacts = create("fieldset", "setting-card");
      contacts.append(create("legend", "", "External contact methods"));
      [
        ["allow_phone", "Allow phone calls"],
        ["allow_whatsapp", "Allow WhatsApp"],
        ["allow_sms", "Allow SMS"],
        ["allow_email", "Show my email address"],
        ["allow_telegram", "Allow Telegram"],
      ].forEach(([name, labelText]) => {
        const label = create("label", "form-check");
        const checkbox = create("input");
        checkbox.type = "checkbox";
        checkbox.name = name;
        checkbox.checked = Boolean(profileData[name]);
        label.append(checkbox, create("span", "", labelText));
        contacts.append(label);
      });
      contacts.append(labeledField("Telegram username", "telegram_username", "text", { maxLength: 32 }));
      $('[name="telegram_username"]', contacts).value = profileData.telegram_username || "";
      profile.append(contacts);
    }
    const save = create("button", "btn btn-primary btn-small"); save.type = "submit"; save.textContent = "Save changes";
    profile.append(save);
    const privacy = create("div", "setting-card");
    privacy.append(create("h3", "", "Your privacy, your way"));
    [
      ["email", "Email updates", "Important account and community updates."],
      ["messages", "Message notifications", "Know when a neighbour replies."],
      ["priceChanges", "Saved listing updates", "Hear about price changes to saved finds."],
    ].forEach(([key, title, description]) => {
      const row = create("div", "toggle-row");
      const label = create("label");
      label.append(create("strong", "", title), create("small", "", description));
      const checkbox = create("input", "switch"); checkbox.type = "checkbox"; checkbox.checked = savedPrivacy[key]; checkbox.dataset.action = "privacy-toggle"; checkbox.dataset.key = key;
      checkbox.setAttribute("aria-label", title);
      row.append(label, checkbox); privacy.append(row);
    });
    const passwordForm = create("form", "setting-card"); passwordForm.id = "password-change-form";
    passwordForm.append(create("h3", "", "Change password"));
    passwordForm.append(labeledField("Current password", "old_password", "password", { autocomplete: "current-password" }));
    passwordForm.append(labeledField("New password", "new_password", "password", { autocomplete: "new-password" }));
    const passwordSubmit = create("button", "btn btn-outline btn-small"); passwordSubmit.type = "submit"; passwordSubmit.textContent = "Update password";
    passwordForm.append(passwordSubmit);
    const data = create("div", "setting-card");
    data.append(create("h3", "", "Your data belongs to you"), create("p", "", "You can request a copy of your account data or ask the team for help with account deletion."));
    const contact = create("a", "btn btn-outline btn-small"); contact.href = routeHref("/contact"); contact.append(icon("bi-envelope"), document.createTextNode("Contact our team"));
    data.append(contact);
    grid.append(profile, privacy, passwordForm, data);
    content.append(grid);
  }

  async function renderAdminSection(content, section) {
    if (section === "support") {
      await renderSupport(content, true);
      return;
    }
    const routeBySection = {
      users: "users",
      approvals: "pending-approvals",
      sellers: "sellers",
      products: "products",
      conversations: "conversations",
      categories: "categories",
      "category-suggestions": "category-suggestions",
      reports: "reports",
      reviews: "reviews",
      messages: "message-reports",
      security: "security-activity",
      audit: "audit-logs",
      settings: "settings",
      announcements: "announcements",
    };
    const resource = section === "overview" || section === "analytics" ? "analytics" : routeBySection[section] || section;
    const pageData = section === "notifications"
      ? null
      : await window.SokoDashboard.adminPage(resource, Number(currentRoute?.query.get("page") || 1));
    const response = section === "notifications"
      ? await window.SokoDashboard.notifications()
      : pageData.results || pageData;
    const panel = create("div", "panel");
    const superAdmin = Boolean((await window.SokoAuth.currentUser())?.admin_role === "super_admin");
    if (section === "overview" || section === "analytics") {
      const labels = {
        users: ["bi-people", "Total accounts"],
        active_users: ["bi-person-check", "Active accounts"],
        active_sellers: ["bi-shop", "Active sellers"],
        active_products: ["bi-box-seam", "Live listings"],
        open_reports: ["bi-flag", "Open reports"],
        reviews: ["bi-star", "Visible reviews"],
        announcements: ["bi-megaphone", "Published announcements"],
        support_conversations: ["bi-headset", "Open support conversations"],
      };
      const metrics = create("div", "metric-grid admin-metrics");
      Object.entries(labels).forEach(([key, [iconName, label]]) => {
        if (typeof response[key] === "number") metrics.append(metricCard(iconName, response[key], label));
      });
      content.append(metrics);
    }
    if (superAdmin && (section === "overview" || section === "analytics")) {
      const updates = await window.SokoDashboard.notifications();
      const unread = updates.filter((item) => item.unread).slice(0, 5);
      const approvals = create("a", "btn btn-outline btn-small", `Pending approvals (${response.pending_approvals || 0})`);
      approvals.href = routeHref("/admin/approvals");
      const reports = create("a", "btn btn-outline btn-small", `Open reports (${response.open_reports || 0})`);
      reports.href = routeHref("/admin/reports");
      const notificationPanel = create("div", "panel");
      notificationPanel.append(create("h2", "", "Admin updates"), approvals, reports);
      unread.forEach((item) => notificationPanel.append(activityRow("bi-bell", item.title, item.text)));
      const allNotifications = create("a", "text-link", "View notifications");
      allNotifications.href = routeHref("/admin/notifications");
      notificationPanel.append(allNotifications);
      content.append(notificationPanel);
    }
    if (superAdmin && ["users", "products", "conversations", "categories", "announcements"].includes(section)) {
      const form = create("form", "panel admin-create-form");
      form.id = "admin-create-form";
      form.dataset.resource = section;
      form.append(create("h2", "", ({
        users: "Create an account",
        products: "Add a marketplace listing",
        conversations: "Open a conversation",
        categories: "Create a category",
        announcements: "Publish an announcement",
      })[section]));
      if (section === "users") {
        form.append(labeledField("Email address", "email", "email"));
        form.append(labeledField("Temporary password", "password", "password", { autocomplete: "new-password" }));
        form.append(labeledField("First name", "first_name", "text", { required: false }));
        form.append(labeledField("Last name", "last_name", "text", { required: false }));
        const role = create("select", "form-select");
        role.name = "admin_role";
        [["", "Regular member"], ["moderator", "Moderator"], ["support_admin", "Support administrator"]]
          .forEach(([value, label]) => role.append(new Option(label, value)));
        form.append(makeFilterField("Access role", role, "admin-user-role"));
      } else if (section === "products") {
        form.append(create("p", "form-hint", "This listing will be owned by SokoMtaani and shown as a team listing."));
        form.append(labeledField("Category name", "category"));
        form.append(labeledField("Listing title", "name"));
        form.append(labeledField("Description", "description", "text", { multiline: true, rows: 3 }));
        form.append(labeledField("Price (KES)", "price", "number"));
        const condition = create("select", "form-select"); condition.name = "condition";
        [["new", "New"], ["like_new", "Like new"], ["gently_used", "Gently used"]].forEach(([value, label]) => condition.append(new Option(label, value)));
        form.append(makeFilterField("Condition", condition, "admin-product-condition"));
        form.append(labeledField("County", "county"));
        form.append(labeledField("Town", "town"));
      } else if (section === "conversations") {
        form.append(labeledField("Buyer account UUID", "buyer_id"));
        form.append(labeledField("Seller account UUID", "seller_id"));
        form.append(labeledField("Listing UUID (optional)", "product_id", "text", { required: false }));
      } else if (section === "categories") {
        form.append(labeledField("Category name", "name", "text", { maxLength: 80 }));
        form.append(labeledField("Description", "description", "text", { multiline: true, rows: 2, required: false }));
      } else {
        form.append(labeledField("Announcement title", "title", "text", { maxLength: 180 }));
        form.append(labeledField("Announcement", "body", "text", { multiline: true, rows: 4, maxLength: 5000 }));
        const published = create("input");
        published.type = "checkbox";
        published.name = "is_published";
        published.checked = true;
        form.append(makeFilterField("Publish now", published, "announcement-published"));
      }
      const submit = create("button", "btn btn-primary"); submit.type = "submit"; submit.textContent = "Create";
      form.append(submit);
      content.append(form);
    }
    if (superAdmin && section === "settings" && response.site_content) {
      const form = create("form", "panel");
      form.id = "admin-settings-form";
      form.append(create("h2", "", "Community and contact information"));
      const settings = response.site_content;
      [
        ["Contact email", "contact_email", "email"],
        ["Contact phone", "contact_phone", "text"],
        ["Community hours", "community_hours", "text"],
        ["About title", "about_title", "text"],
        ["About introduction", "about_intro", "textarea"],
        ["Team title", "team_title", "text"],
        ["Team information", "team_information", "textarea"],
      ].forEach(([label, name, type]) => {
        const field = labeledField(label, name, type === "textarea" ? "text" : type, { multiline: type === "textarea", required: false, rows: 3 });
        const input = field.querySelector(`[name="${name}"]`);
        input.value = settings[name] || "";
        form.append(field);
      });
      const save = create("button", "btn btn-primary"); save.type = "submit"; save.textContent = "Save site information";
      form.append(save);
      content.append(form);
    }
    const table = create("div", "admin-record-list");
    const records = Array.isArray(response)
      ? response
      : section === "overview" || section === "analytics"
        ? []
        : Object.entries(response || {}).map(([name, value]) => ({ name, value }));
    records.forEach((item) => {
      const label = item.name || item.title || item.email || item.display_name || item.id || item.metric || "Marketplace record";
      const detail = item.status || item.role || item.description || item.created_at || item.value || "";
      const row = create("div", "listing-row admin-record-row");
      row.dataset.searchText = Object.values(item).map((value) => String(value ?? "")).join(" ").toLowerCase();
      row.append(create("span", "avatar", initials(label)));
      row.append(appendAll(create("div"), [create("strong", "", label), create("small", "", String(detail))]));
      const actionByResource = {
        reports: ["review", "Assign"],
        "message-reports": ["review", "Assign"],
        "pending-approvals": ["approve", "Approve account"],
        products: [item.status === "active" ? "pause" : "activate", item.status === "active" ? "Pause" : "Activate"],
        users: [item.status === "active" ? "suspend" : "reactivate", item.status === "active" ? "Suspend" : "Reactivate"],
        sellers: [item.status === "active" ? "suspend" : "activate", item.status === "active" ? "Suspend" : "Activate"],
        reviews: [item.status === "visible" ? "hide" : "restore", item.status === "visible" ? "Hide" : "Restore"],
        categories: [item.status === "active" ? "disable" : "enable", item.status === "active" ? "Disable" : "Enable"],
        "category-suggestions": [item.status === "pending" ? "approve" : "dismiss", item.status === "pending" ? "Approve request" : "Dismiss request"],
      };
      if (section === "notifications" && item.id && !item.read_at) {
        const markRead = create("button", "btn btn-outline btn-small", "Mark read");
        markRead.type = "button";
        markRead.dataset.action = "mark-notification";
        markRead.dataset.id = item.id;
        row.append(markRead);
      }
      if (item.id && actionByResource[resource]
        && (resource !== "category-suggestions" || item.status === "pending")) {
        const actions = ["reports", "message-reports"].includes(resource)
          && ["user", "product", "comment", "review", "message"].includes(item.target_type)
          ? [[...actionByResource[resource]], ["suspend", "Suspend reported account"]]
          : (resource === "users" || resource === "pending-approvals") && item.status === "pending_approval"
            ? [["approve", "Approve account"]]
            : [[...actionByResource[resource]]];
        if (resource === "users" && superAdmin && item.status !== "pending_approval") {
          actions.push(["deactivate", "Deactivate account"], ["delete", "Delete account"]);
        }
        if (resource === "products" && superAdmin) {
          actions.push(["delete", "Delete listing"]);
        }
        actions.forEach(([actionName, actionLabel]) => {
          const action = create("button", "btn btn-outline btn-small", actionLabel);
          action.type = "button";
          action.dataset.action = "admin-review";
          action.dataset.id = item.id;
          action.dataset.resource = resource === "pending-approvals" ? "users" : resource;
          action.dataset.adminAction = actionName;
          row.append(action);
        });
        if (resource === "message-reports" && item.status === "assigned" && item.assigned_to) {
          const evidence = create("button", "btn btn-outline btn-small", "View reported message");
          evidence.type = "button";
          evidence.dataset.action = "admin-message-evidence";
          evidence.dataset.id = item.id;
          row.append(evidence);
        }
      }
      let editForm = null;
      if (superAdmin && item.id && ["users", "products", "announcements"].includes(resource)) {
        const edit = create("button", "btn btn-outline btn-small", "Edit");
        edit.type = "button";
        edit.dataset.action = "toggle-admin-edit";
        edit.dataset.resource = resource;
        edit.dataset.id = item.id;
        row.append(edit);

        editForm = create("form", "panel admin-inline-edit");
        editForm.id = `admin-edit-${resource}-${item.id}`;
        editForm.hidden = true;
        editForm.dataset.resource = resource;
        editForm.dataset.id = item.id;
        const fields = resource === "users"
          ? [
            ["Email address", "email", "email", item.email],
            ["First name", "first_name", "text", item.first_name],
            ["Last name", "last_name", "text", item.last_name],
          ]
          : resource === "products"
            ? [
            ["Listing title", "name", "text", item.name],
            ["Description", "description", "text", item.description],
            ["Category", "category", "text", item.category],
            ["Price (KES)", "price", "number", item.price],
            ["Condition", "condition", "text", item.condition],
            ["County", "county", "text", item.county],
            ["Town", "town", "text", item.town],
            ]
            : [
              ["Announcement title", "title", "text", item.title],
              ["Announcement", "body", "text", item.body],
            ];
        fields.forEach(([label, name, type, value]) => {
          const field = labeledField(label, name, type, {
            multiline: name === "description",
            rows: 3,
          });
          field.querySelector(`[name="${name}"]`).value = value ?? "";
          editForm.append(field);
        });
        if (resource === "announcements") {
          const published = create("input");
          published.type = "checkbox";
          published.name = "is_published";
          published.checked = item.is_published;
          editForm.append(makeFilterField("Published", published, `announcement-published-${item.id}`));
        }
        const save = create("button", "btn btn-primary btn-small", "Save changes");
        save.type = "submit";
        const cancel = create("button", "btn btn-outline btn-small", "Cancel");
        cancel.type = "button";
        cancel.dataset.action = "close-admin-edit";
        cancel.dataset.resource = resource;
        cancel.dataset.id = item.id;
        editForm.append(save, cancel);
      }
      table.append(row);
      if (editForm) table.append(editForm);
    });
    if (!records.length) table.append(create("p", "", "No records to display."));
    panel.append(table);
    content.append(panel);
    if (pageData?.results && pageData.count > 0) {
      const currentPage = Number(currentRoute?.query.get("page") || 1);
      const pagination = create("div", "admin-pagination");
      pagination.append(create("span", "", `${pageData.count.toLocaleString()} records · page ${currentPage}`));
      const controls = create("div");
      if (pageData.previous) {
        const previous = create("button", "btn btn-outline btn-small", "Previous");
        previous.type = "button";
        previous.dataset.action = "admin-page";
        previous.dataset.page = String(currentPage - 1);
        controls.append(previous);
      }
      if (pageData.next) {
        const next = create("button", "btn btn-outline btn-small", "Next");
        next.type = "button";
        next.dataset.action = "admin-page";
        next.dataset.page = String(currentPage + 1);
        controls.append(next);
      }
      pagination.append(controls);
      content.append(pagination);
    }
  }

  function renderMessagesStandalone(user) {
    const wrap = create("div", "container-wide section-tight");
    wrap.append(create("h1", "page-heading", "Your conversations"));
    renderMessages(wrap).then(() => main.replaceChildren(wrap)).catch(showError);
  }

  function renderNotFound(title, description) {
    const page = create("div", "container-wide section");
    renderNotFoundInto(page, title, description);
    main.replaceChildren(page);
  }

  function renderNotFoundInto(parent, title, description = "This page isn't available right now.") {
    const empty = create("div", "empty-state");
    empty.append(icon("bi-compass"), create("h2", "", title), create("p", "", description));
    const link = create("a", "btn btn-primary"); link.href = routeHref("/home"); link.textContent = "Back to SokoMtaani";
    empty.append(link); parent.append(empty);
  }

  async function renderInfoPage(path) {
    const siteInfo = path === "/about" ? await getSiteInfo() : null;
    const data = {
      "/about": ["Good things happen close to home.", "SokoMtaani is a community marketplace built around the simple idea that the things we need — and the people we want to meet — are often already nearby.", [
        ["A marketplace with a neighbourhood feel", "Discover pre-loved treasures, locally made goods and everyday essentials from people across Kenya. Browse by category, price and place to find items that fit your life."],
        ["People first, always", "SokoMtaani helps buyers and sellers find each other. People communicate directly and independently agree on inspections, collection, delivery and payment. The platform does not process payments."],
        ["A safer way to meet", "We encourage clear descriptions, respectful conversations and sensible meetups. Our community guidelines and reporting tools help us make room for good experiences."],
      ]],
      "/terms": ["Terms of service", "These plain-language terms explain how the SokoMtaani marketplace works. They are a guide to using the service, not legal advice.", [
        ["A place to connect", "SokoMtaani provides listing and communication tools. We do not sell listed products, guarantee a product’s condition, hold funds or process payments. Buyers and sellers independently arrange any transaction."],
        ["Your listings and conversations", "Share accurate information and only content you have permission to use. Do not mislead, harass, impersonate others, list prohibited items or misuse the platform."],
        ["Meeting and payment safety", "Inspect an item before agreeing to buy. Choose a sensible public meeting place and make your own payment decisions. Never share passwords or one-time security codes."],
        ["Community moderation", "We may review reported content and take proportionate action under our community standards. Access can be limited when necessary to protect people or the service."],
        ["Questions", "For help with these terms, use our contact page. This draft should receive independent Kenyan legal review before production use."],
      ]],
      "/privacy": ["Your information deserves care.", "This page describes the kinds of information a marketplace may use to make listings, accounts and communication work. Review it with independent legal counsel before launch.", [
        ["Information you provide", "Account details, listings, photos, messages, reviews and support requests are used to provide the service and keep the community working."],
        ["How information is used", "Information may be used for account security, marketplace features, communication preferences, fraud prevention and service improvement. Private messages are not displayed in public listing pages."],
        ["Your choices", "You can manage notification preferences, request access to your information, and contact us about account updates or deletion."],
        ["Security and retention", "We use reasonable safeguards and retain information only as needed for service, security and legal purposes. No online service can promise absolute security."],
        ["Kenya and legal review", "This draft is not a claim of compliance with Kenya’s Data Protection Act, 2019. Data flows, consent, retention, rights handling and cross-border processing need independent review."],
      ]],
      "/safety": ["A few thoughtful ways to stay safe.", "A little care goes a long way when buying or selling with someone new.", [
        ["Keep the conversation on the platform", "Use SokoMtaani messages to ask questions and keep a record of what you agreed. Never share passwords, verification codes or private financial details."],
        ["See the item before you decide", "Ask for recent photos and useful details. Inspect the item in person before agreeing to buy, and trust your instincts if something feels off."],
        ["Meet with care", "Choose a public, familiar place during daylight. Let someone you trust know where you’re going. For large items, plan collection safely."],
        ["Make your own payment arrangements", "SokoMtaani does not process or guarantee payments. Be cautious with advance payment requests, unusual links and pressure to act quickly."],
        ["Report anything concerning", "Use the report option or contact our team if you spot a suspicious listing, unsafe message or conduct that concerns you."],
      ]],
    };
    const [defaultTitle, defaultIntro, sections] = data[path];
    const page = create("article", "content-page");
    const title = siteInfo?.about_title || defaultTitle;
    const intro = siteInfo?.about_intro || defaultIntro;
    page.append(create("span", "eyebrow", path === "/about" ? "Our story" : "SokoMtaani guide"), create("h1", "", title), create("p", "", intro));
    sections.forEach(([heading, paragraph]) => page.append(create("h2", "", heading), create("p", "", paragraph)));
    if (siteInfo?.team_information) {
      page.append(create("h2", "", siteInfo.team_title || "Our community"), create("p", "", siteInfo.team_information));
    }
    main.replaceChildren(page);
  }

  async function renderContact() {
    const siteInfo = await getSiteInfo();
    const page = create("div", "container-wide section");
    const layout = create("div", "settings-grid");
    const form = create("form", "panel"); form.id = "contact-form";
    form.append(create("span", "eyebrow", "We’re here to help"), create("h1", "page-heading", "Say hello."));
    form.append(labeledField("Your name", "name"));
    form.append(labeledField("Email address", "email", "email"));
    form.append(labeledField("What can we help with?", "message", "text", { multiline: true, rows: 5, maxLength: 3000 }));
    const submit = create("button", "btn btn-primary"); submit.type = "submit"; submit.append(icon("bi-send"), document.createTextNode("Send message"));
    form.append(submit);
    const info = create("div", "panel");
    info.append(create("span", "eyebrow", "A little closer to home"), create("h2", "", "Real people, ready to help."), create("p", "", "We aim to reply to community questions within two working days."));
    const emailLink = create("a", "text-link", siteInfo.contact_email || "");
    emailLink.href = `mailto:${siteInfo.contact_email || ""}`;
    const emailRow = create("div", "activity");
    emailRow.append(icon("bi-envelope"), create("strong", "", "Email"), emailLink);
    info.append(emailRow, activityRow("bi-clock", "Community hours", siteInfo.community_hours || ""), activityRow("bi-geo-alt", "Kenya", "Proudly built for our communities"));
    if (siteInfo.contact_phone) info.append(activityRow("bi-telephone", "Phone", siteInfo.contact_phone));
    layout.append(form, info); page.append(layout); main.replaceChildren(page);
  }

  function renderRoute() {
    routeVersion += 1;
    if (routeRendering) return;
    routeRendering = true;
    void renderPendingRoutes();
  }

  async function renderPendingRoutes() {
    try {
      while (renderedRouteVersion !== routeVersion) {
        const version = routeVersion;
        await renderCurrentRoute();
        renderedRouteVersion = version;
      }
    } finally {
      routeRendering = false;
      if (renderedRouteVersion !== routeVersion) renderRoute();
    }
  }

  async function renderCurrentRoute() {
    const { path, query } = parseRoute();
    currentRoute = { path, query };
    main.setAttribute("aria-busy", "true");
    main.innerHTML = '<div class="container-wide loading">A moment…</div>';
    try {
      const user = await window.SokoAuth.currentUser();
      const adminRoute = path.startsWith("/admin");
      document.body.classList.toggle("admin-mode", adminRoute);
      if (adminRoute) {
        header.replaceChildren();
        footer.replaceChildren();
      } else {
        renderFooter();
        await renderHeader(user);
      }
      if (user) await window.SokoProducts.favorites();
      if (path === "/home" || path === "/") await renderHome();
      else if (path === "/search") await renderSearch(query);
      else if (path.startsWith("/category/")) await renderSearch(query, decodeURIComponent(path.slice("/category/".length)));
      else if (path.startsWith("/product/")) await renderProduct(decodeURIComponent(path.slice("/product/".length)));
      else if (path.startsWith("/seller/edit/")) {
        if (!user) navigate("/login");
        else if (user.role === "seller") await renderDashboard(path, user);
        else renderNotFound("This listing editor is for sellers.");
      }
      else if (path.startsWith("/seller/")
        && !["overview", "listings", "create", "analytics", "messages", "support", "notifications", "profile", "settings"].includes(path.split("/")[2])) {
        await renderSeller(decodeURIComponent(path.slice("/seller/".length)));
      }
      else if (path === "/login") renderLogin(false);
      else if (path === "/mfa") renderLogin(true);
      else if (path === "/register") renderRegister();
      else if (path === "/forgot-password") renderForgotPassword();
      else if (path === "/reset-password") renderResetConfirm(query);
      else if (path === "/verify-email") renderVerifyEmail(query);
      else if (path === "/about" || path === "/terms" || path === "/privacy" || path === "/safety") await renderInfoPage(path);
      else if (path === "/contact" || path === "/help") await renderContact();
      else if (path === "/messages") {
        if (!user) navigate("/login");
        else renderMessagesStandalone(user);
      } else if (path === "/seller/create") {
        if (!user) navigate("/login");
        else if (user.role !== "seller" && user.role !== "administrator") {
          const panel = create("div", "container-wide section");
          const empty = create("div", "empty-state"); empty.append(icon("bi-shop"), create("h2", "", "Ready to start selling?"), create("p", "", "Activate seller features on your account to create a listing."));
          const activate = create("button", "btn btn-primary"); activate.type = "button"; activate.dataset.action = "activate-seller"; activate.textContent = "Set up my seller profile";
          empty.append(activate); panel.append(empty); main.replaceChildren(panel);
        } else await renderDashboard("/seller/create", user);
      } else if (["/buyer", "/seller", "/admin"].some((base) => path === base || path.startsWith(`${base}/`))) {
        if (!user) navigate("/login");
        else if (path.startsWith("/admin") && !isAdmin(user)) {
          renderNotFound("This area is for authorised administrators.", "Marketplace administration is enforced by the backend, not by this interface.");
        } else if (path === "/admin" && user.admin_role !== "super_admin") {
          navigate(adminHome(user));
        } else if (path.startsWith("/seller") && user.role !== "seller" && user.role !== "administrator") {
          navigate("/seller/create");
        } else await renderDashboard(path, user);
      } else if (path === "/favourites") {
        if (!user) navigate("/login"); else navigate("/buyer/favourites");
      } else renderNotFound("We couldn't find that page.");
    } catch (error) {
      renderErrorPage(error);
    } finally {
      main.setAttribute("aria-busy", "false");
      main.focus({ preventScroll: true });
    }
  }

  function renderErrorPage(error) {
    const page = create("div", "container-wide section");
    const empty = create("div", "empty-state"); empty.append(icon("bi-cloud-exclamation"), create("h2", "", "We couldn’t load this page"), create("p", "", error.message));
    const retry = create("button", "btn btn-primary"); retry.type = "button"; retry.dataset.action = "retry"; retry.textContent = "Try again";
    empty.append(retry); page.append(empty); main.replaceChildren(page);
  }

  async function withBusy(form, callback) {
    const button = form.querySelector('button[type="submit"]');
    const old = button?.textContent || "";
    if (button) { button.disabled = true; button.textContent = "Please wait…"; }
    try { await callback(); }
    catch (error) {
      formAlert(form, error.message);
      if (["account_pending_approval", "account_suspended", "account_unavailable"].includes(error.data?.code)) {
        const contact = create("a", "btn btn-outline btn-small", "Contact support");
        const contactEmail = error.data.contact_email || "";
        contact.href = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contactEmail)
          ? `mailto:${contactEmail}?subject=${encodeURIComponent("SokoMtaani account assistance")}`
          : routeHref("/contact");
        contact.style.marginTop = "12px";
        $(".form-alert", form).append(document.createElement("br"), contact);
      }
    }
    finally { if (button) { button.disabled = false; button.textContent = old; } }
  }

  function valuesFromForm(form) {
    return Object.fromEntries(new FormData(form).entries());
  }

  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.id === "top-search-form" || form.id === "hero-search-form") {
      event.preventDefault();
      const data = new FormData(form);
      navigate(`/search?${new URLSearchParams({ search: data.get("search") || "" })}`);
      return;
    }
    if (form.id === "search-filters") {
      event.preventDefault();
      const data = new FormData(form);
      data.set("sort", $("#search-sort")?.value || "newest");
      navigate(`/search?${new URLSearchParams(data)}`);
      return;
    }
    if (form.id === "login-form") {
      event.preventDefault();
      await withBusy(form, async () => {
        const result = await window.SokoAuth.login(valuesFromForm(form));
        if (result.status === 202) { navigate("/mfa"); return; }
        showToast("You’re signed in. Welcome back!");
        navigate(result.data.role === "administrator" ? "/admin" : result.data.role === "seller" ? "/seller" : "/buyer");
      });
      return;
    }
    if (form.id === "mfa-form") {
      event.preventDefault();
      await withBusy(form, async () => {
        const result = await window.SokoAuth.verifyMfa(valuesFromForm(form).code);
        showToast("Authenticator confirmed. You’re securely signed in.");
        navigate(isAdmin(result.data) ? adminHome(result.data) : "/seller");
      });
      return;
    }
    if (form.id === "register-form") {
      event.preventDefault();
      await withBusy(form, async () => {
        const values = valuesFromForm(form);
        const result = await window.SokoAuth.register({
          email: values.email,
          password: values.password,
          first_name: values.first_name,
          last_name: values.last_name,
          account_mode: values.account_mode,
        });
        formAlert(form, `Account created for ${result.data.email}. You’re signed in and ready to browse.`, true);
        navigate(isAdmin(result.data) ? adminHome(result.data) : "/buyer");
      });
      return;
    }
    if (form.id === "reset-request-form") {
      event.preventDefault();
      await withBusy(form, async () => {
        await window.SokoAuth.requestPasswordReset(valuesFromForm(form).email);
        formAlert(form, "If an account exists for that email, reset instructions are on their way.", true);
      });
      return;
    }
    if (form.id === "reset-confirm-form") {
      event.preventDefault();
      await withBusy(form, async () => {
        await window.SokoAuth.confirmPasswordReset(valuesFromForm(form));
        formAlert(form, "Your password was updated. You can now sign in.", true);
      });
      return;
    }
    if (form.id === "verify-email-form") {
      event.preventDefault();
      await withBusy(form, async () => {
        await window.SokoAuth.verifyEmail(valuesFromForm(form).token);
        formAlert(form, "Your email is verified. You can now log in.", true);
      });
      return;
    }
    if (form.id === "create-product-form" || form.id === "edit-product-form") {
      event.preventDefault();
      await withBusy(form, async () => {
        if ($('[name="category"]', form)?.value === "__custom__") {
          if (form.id === "edit-product-form") throw new Error("Choose an existing category before saving an edited listing.");
          const name = $('[name="custom_category"]', form)?.value.trim();
          if (!name) throw new Error("Enter the name of the category you want us to review.");
          await window.SokoDashboard.suggestCategory({ name });
          formAlert(form, "Your category request was sent for review. You can publish this listing after it is approved.", true);
          return;
        }
        const files = [...($('[name="images"]', form)?.files || [])];
        if (files.length > 6) throw new Error("Choose up to six photos.");
        const allowed = ["image/jpeg", "image/png", "image/webp"];
        if (files.some((file) => !allowed.includes(file.type) || file.size > 5 * 1024 * 1024)) {
          throw new Error("Each photo must be JPEG, PNG or WebP and no larger than 5 MB.");
        }
        const data = new FormData(form);
        data.set("negotiable", String($('[name="negotiable"]', form)?.checked || false));
        if (form.id === "edit-product-form") {
          await window.SokoProducts.update(form.dataset.productId, data);
          showToast("Your listing has been updated.");
        } else {
          await window.SokoProducts.create(data);
          showToast("Your listing has been added.");
        }
        navigate("/seller/listings");
      });
      return;
    }
    if (form.id === "message-compose") {
      event.preventDefault();
      const data = new FormData(form);
      await withBusy(form, async () => {
        const attachment = data.get("attachment");
        const file = attachment instanceof File && attachment.size ? attachment : null;
        if (file && (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 5 * 1024 * 1024)) {
          throw new Error("Attachment must be JPEG, PNG or WebP and no larger than 5 MB.");
        }
        await window.SokoMessages.send(form.dataset.id, String(data.get("message") || "").trim(), file);
        await renderRoute();
      });
      return;
    }
    if (form.id === "comment-form") {
      event.preventDefault();
      await withBusy(form, async () => {
        const product = form.dataset.product;
        const item = await window.SokoProducts.addComment(form.dataset.product, valuesFromForm(form).comment);
        const items = comments.get(product) || [];
        comments.set(product, [item, ...items]);
        showToast("Your question was added.");
        await renderRoute();
      });
      return;
    }
    if (form.id === "seller-review-form") {
      event.preventDefault();
      await withBusy(form, async () => {
        if (!await window.SokoAuth.currentUser()) {
          navigate("/login");
          return;
        }
        const values = valuesFromForm(form);
        const review = await window.SokoProducts.addSellerReview(form.dataset.seller, values);
        const key = String(form.dataset.seller);
        sellerReviews.set(key, [review, ...(sellerReviews.get(key) || [])]);
        showToast("Your community review was shared.");
        await renderRoute();
      });
      return;
    }
    if (form.id === "profile-form") {
      event.preventDefault();
      await withBusy(form, async () => {
        const isSeller = form.dataset.seller === "true";
        const values = valuesFromForm(form);
        if (isSeller) {
          ["allow_phone", "allow_whatsapp", "allow_sms", "allow_email", "allow_telegram"].forEach((key) => {
            values[key] = Boolean($(`[name="${key}"]`, form)?.checked);
          });
        }
        await window.SokoDashboard.updateProfile(values, isSeller);
        showToast("Profile updated.");
      });
      return;
    }
    if (form.id === "password-change-form") {
      event.preventDefault();
      await withBusy(form, async () => {
        await window.SokoAuth.changePassword(valuesFromForm(form));
        showToast("Password updated.");
        form.reset();
      });
      return;
    }
    if (form.id === "contact-form") {
      event.preventDefault();
      await withBusy(form, async () => {
        const values = valuesFromForm(form);
        const subject = encodeURIComponent(`SokoMtaani enquiry from ${values.name}`);
        const body = encodeURIComponent(`${values.message}\n\nReply to: ${values.email}`);
        const siteInfo = await getSiteInfo();
        location.href = `mailto:${siteInfo.contact_email || ""}?subject=${subject}&body=${body}`;
        formAlert(form, "Your email app should open with the message ready to send.", true);
      });
      return;
    }
    if (form.id === "support-compose-form") {
      event.preventDefault();
      await withBusy(form, async () => {
        const values = valuesFromForm(form);
        await window.SokoDashboard.createSupportConversation(values.subject, values.message);
        await renderRoute();
        showToast("Your message was sent to SokoMtaani support.");
      });
      return;
    }
    if (form.matches(".support-reply-form")) {
      event.preventDefault();
      await withBusy(form, async () => {
        await window.SokoDashboard.replyToSupport(form.dataset.id, valuesFromForm(form).body);
        await renderRoute();
      });
      return;
    }
    if (form.id === "admin-create-form") {
      event.preventDefault();
      await withBusy(form, async () => {
        const values = valuesFromForm(form);
        if (form.dataset.resource === "products") values.price = Number(values.price);
        if (form.dataset.resource === "users" && !values.admin_role) delete values.admin_role;
        if (form.dataset.resource === "announcements") {
          values.is_published = Boolean($('[name="is_published"]', form)?.checked);
        }
        if (form.dataset.resource === "conversations" && !values.product_id) delete values.product_id;
        const response = await window.SokoDashboard.createAdminRecord(form.dataset.resource, values);
        form.reset();
        formAlert(form, "Record created successfully.", true);
        if (response.status === 201 || response.status === 200) await renderRoute();
      });
      return;
    }
    if (form.id === "admin-settings-form") {
      event.preventDefault();
      await withBusy(form, async () => {
        await window.SokoDashboard.saveAdminSettings(valuesFromForm(form));
        siteInfoCache = null;
        formAlert(form, "Community and contact information saved.", true);
      });
      return;
    }
    if (form.matches(".admin-inline-edit")) {
      event.preventDefault();
      await withBusy(form, async () => {
        const values = valuesFromForm(form);
        if (form.dataset.resource === "announcements") {
          values.is_published = Boolean($('[name="is_published"]', form)?.checked);
        }
        await window.SokoDashboard.updateAdminRecord(
          form.dataset.resource,
          form.dataset.id,
          values,
        );
        showToast("Changes saved.");
        await renderRoute();
      });
    }
  });

  document.addEventListener("click", async (event) => {
    const target = event.target.closest("[data-action]");
    if (!target) return;
    const action = target.dataset.action;
    try {
      if (action === "admin-sidebar-toggle") {
        const shell = $(".admin-shell");
        if (window.matchMedia("(max-width: 900px)").matches) {
          shell?.classList.toggle("mobile-open");
        } else {
          shell?.classList.toggle("is-collapsed");
        }
      } else if (action === "admin-profile-menu") {
        const menu = $(".admin-profile-dropdown", target.parentElement);
        const expanded = target.getAttribute("aria-expanded") === "true";
        target.setAttribute("aria-expanded", String(!expanded));
        if (menu) menu.hidden = expanded;
      } else if (action === "admin-page") {
        const { path, query } = parseRoute();
        query.set("page", target.dataset.page);
        navigate(`${path}?${query}`);
      } else if (action === "favorite") {
        const selected = await window.SokoProducts.toggleFavorite(target.dataset.id);
        target.classList.toggle("is-favorite", selected);
        target.setAttribute("aria-pressed", String(selected));
        const heart = target.querySelector(".bi");
        if (heart) heart.className = `bi ${selected ? "bi-heart-fill" : "bi-heart"}`;
        showToast(selected ? "Saved to your favourites." : "Removed from your favourites.");
      } else if (action === "logout") {
        await window.SokoAuth.logout(); showToast("You’re signed out."); navigate("/home");
      } else if (action === "toggle-password") {
        const control = target.closest(".password-control");
        const input = control?.querySelector("input");
        if (!input) return;
        const visible = input.type === "password";
        input.type = visible ? "text" : "password";
        target.setAttribute("aria-label", visible ? "Hide password" : "Show password");
        target.setAttribute("aria-pressed", String(visible));
        target.replaceChildren(icon(visible ? "bi-eye-slash" : "bi-eye"));
      } else if (action === "toggle-admin-edit") {
        const editor = document.getElementById(`admin-edit-${target.dataset.resource}-${target.dataset.id}`);
        if (editor) editor.hidden = !editor.hidden;
      } else if (action === "close-admin-edit") {
        const editor = document.getElementById(`admin-edit-${target.dataset.resource}-${target.dataset.id}`);
        if (editor) editor.hidden = true;
      } else if (action === "page") {
        const { query } = parseRoute(); query.set("page", target.dataset.page);
        navigate(`/search?${query}`);
      } else if (action === "clear-filters") navigate("/search");
      else if (action === "toggle-filters") $(".filter-panel")?.classList.toggle("open");
      else if (action === "mobile-menu") $(".subnav")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      else if (action === "add-cart-item") {
        if (!await window.SokoAuth.currentUser()) { navigate("/login"); return; }
        await window.SokoDashboard.addToCart(target.dataset.id);
        showToast("Added to your cart.");
      } else if (action === "remove-cart-item") {
        await window.SokoDashboard.removeFromCart(target.dataset.id);
        await renderRoute();
        showToast("Removed from your cart.");
      }
      else if (action === "retry") renderRoute();
      else if (action === "select-conversation") {
        activeConversation = target.dataset.id;
        const content = $(".dashboard-content") || main;
        if (content === main) renderMessagesStandalone(await window.SokoAuth.currentUser());
        else await renderMessages(content);
      } else if (action === "message-back") $(".message-layout")?.classList.remove("show-conversation");
      else if (action === "message-seller") {
        if (!await window.SokoAuth.currentUser()) { navigate("/login"); return; }
        const product = await window.SokoProducts.get(target.dataset.product);
        if (!product) throw new Error("This listing is no longer available.");
        const conversation = await window.SokoMessages.start(product);
        activeConversation = conversation.id;
        navigate("/messages");
      } else if (action === "seller-contact") {
        if (!await window.SokoAuth.currentUser()) navigate("/login");
        else {
          const conversation = await window.SokoMessages.startSeller({
            id: target.dataset.seller,
            display_name: target.dataset.sellerName,
          });
          activeConversation = conversation.id;
          navigate("/messages");
        }
      } else if (action === "report-conversation") {
        await window.SokoMessages.report(target.dataset.userId);
        showToast("Thank you. The member was reported for review.");
      } else if (action === "block-conversation") {
        const userId = target.dataset.userId;
        if (!userId) throw new Error("This conversation does not include a blockable member ID.");
        await window.SokoMessages.block(userId);
        showToast("Member blocked.");
        navigate("/buyer/blocked");
      } else if (action === "unblock-user") {
        await window.SokoDashboard.unblockUser(target.dataset.id);
        showToast("Member unblocked.");
        await renderRoute();
      }
      else if (action === "activate-seller") {
        const user = await window.SokoAuth.currentUser();
        if (user) {
          await window.SokoAuth.activateSeller();
          showToast("Your seller profile is active.");
          navigate("/seller");
        } else navigate("/login");
      } else if (action === "copy-mfa") {
        const uri = $(".mfa-uri")?.textContent || "";
        await navigator.clipboard.writeText(uri);
        showToast("Setup link copied.");
      } else if (action === "helpful") {
        await window.SokoProducts.voteComment(target.dataset.product, target.dataset.id);
        showToast("Thanks for sharing what was helpful.");
      } else if (action === "report-content") {
        await window.SokoProducts.reportContent(target.dataset.type, target.dataset.id);
        showToast("Thank you. The content was reported for review.");
      }
      else if (action === "mark-notification") {
        await window.SokoDashboard.markNotificationRead(target.dataset.id);
        showToast("Notification marked as read.");
        await renderRoute();
      } else if (action === "delete-notification") {
        await window.SokoDashboard.deleteNotification(target.dataset.id);
        showToast("Notification deleted.");
        await renderRoute();
      } else if (action === "listing-action") {
        await window.SokoProducts.updateStatus(target.dataset.id, target.dataset.status);
        showToast("Listing availability updated.");
        await renderRoute();
      }
      else if (action === "admin-review") {
        await window.SokoDashboard.adminAction(target.dataset.resource, target.dataset.id, target.dataset.adminAction);
        showToast("Admin action recorded.");
        await renderRoute();
      } else if (action === "admin-message-evidence") {
        const evidence = await window.SokoDashboard.adminMessageEvidence(target.dataset.id);
        showToast(evidence.message.content || "Reported message contains an attachment.");
      }
    } catch (error) { showError(error); }
  });

  document.addEventListener("change", (event) => {
    const target = event.target;
    if (target.id === "admin-period") {
      const { path, query } = parseRoute();
      query.set("period", target.value);
      navigate(`${path}?${query}`);
    } else if (target.id === "search-sort") {
      const { query } = parseRoute();
      query.set("sort", target.value);
      navigate(`/search?${query}`);
    }
    if (target.id === "product-images") {
      pendingProductImages.forEach((url) => URL.revokeObjectURL(url));
      const selectedFiles = [...target.files];
      if (selectedFiles.length > 6 || selectedFiles.some((file) => !["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 5 * 1024 * 1024)) {
        target.value = "";
        showToast("Choose up to six JPEG, PNG or WebP images no larger than 5 MB each.", "error");
        return;
      }
      pendingProductImages = selectedFiles.map((file) => URL.createObjectURL(file));
      const preview = $("#image-preview");
      preview?.replaceChildren();
      pendingProductImages.forEach((url) => {
        const img = create("img"); setMediaSource(img, url); img.alt = "Selected listing photo preview"; preview?.append(img);
      });
      if (pendingProductImages[0]) {
        const previewImage = $(".product-preview img");
        if (previewImage) setMediaSource(previewImage, pendingProductImages[0]);
      }
    }
    if (target.name === "attachment") {
      const file = target.files?.[0];
      if (!file) return;
      if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 5 * 1024 * 1024) {
        target.value = "";
        $("#attachment-status").textContent = "";
        showToast("Attachment must be JPEG, PNG or WebP and no larger than 5 MB.", "error");
        return;
      }
      $("#attachment-status").textContent = file.name;
    }
    if (target.dataset.action === "privacy-toggle") {
      const oldValue = savedPrivacy[target.dataset.key];
      savedPrivacy[target.dataset.key] = target.checked;
      window.SokoDashboard.savePreferences({
        email: savedPrivacy.email,
        messages: savedPrivacy.messages,
        price_changes: savedPrivacy.priceChanges,
      }).then(() => showToast("Your notification preference was updated."))
        .catch((error) => {
          savedPrivacy[target.dataset.key] = oldValue;
          target.checked = oldValue;
          showError(error);
        });
    }
  });

  document.addEventListener("input", (event) => {
    if (event.target.id === "admin-page-search") {
      const term = event.target.value.trim().toLowerCase();
      $$(".admin-record-row").forEach((row) => {
        row.hidden = term.length > 0 && !row.dataset.searchText.includes(term);
      });
      return;
    }
    const form = event.target.closest("#create-product-form");
    if (!form) return;
    const name = $('[name="name"]', form)?.value || "Your listing title";
    const price = $('[name="price"]', form)?.value || "0";
    const county = $('[name="county"]', form)?.value || "Your county";
    const town = $('[name="town"]', form)?.value || "Your town";
    const description = $('[name="description"]', form)?.value || "Your description will appear here.";
    $(".preview-name", form).textContent = name;
    $(".preview-price", form).textContent = currency(price);
    $(".preview-location", form).textContent = `${town}, ${county}`;
    $(".product-preview p", form).textContent = description.slice(0, 120);
  });

  function initializeApp() {
    if (appInitialized) return;
    appInitialized = true;
    renderFooter();
    renderRoute();
  }

  window.addEventListener("hashchange", renderRoute);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeApp, { once: true });
  } else {
    initializeApp();
  }
})();
