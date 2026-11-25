import { mkdir, writeFile } from "node:fs/promises";

const origin = process.env.PAPERLOOP_AUDIT_URL ?? "http://127.0.0.1:8000/accounts/landing/";
const outputDir = process.env.PAPERLOOP_AUDIT_DIR ?? "docs/audits/paperloop-landing";
const allThemes = [
  { name: "light", preference: "light" },
  { name: "dark", preference: "dark" },
  { name: "forest", preference: "forest" },
  { name: "system-light", preference: "system", colorScheme: "light" },
  { name: "system-dark", preference: "system", colorScheme: "dark" },
];
const allViewports = [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "laptop", width: 1280, height: 900 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "mobile", width: 390, height: 844 },
];
const themes = process.env.PAPERLOOP_AUDIT_THEMES
  ? allThemes.filter(({ name }) => process.env.PAPERLOOP_AUDIT_THEMES.split(",").includes(name))
  : allThemes;
const viewports = process.env.PAPERLOOP_AUDIT_VIEWPORTS
  ? allViewports.filter(({ name }) => process.env.PAPERLOOP_AUDIT_VIEWPORTS.split(",").includes(name))
  : allViewports;

await mkdir(outputDir, { recursive: true });
const targetResponse = await fetch("http://127.0.0.1:9229/json/new?about:blank", { method: "PUT" });
if (!targetResponse.ok) throw new Error(`Could not create Chrome tab (${targetResponse.status})`);
const target = await targetResponse.json();
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});
let nextId = 1;
const pending = new Map();
const events = new Map();
socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    message.error ? reject(new Error(message.error.message)) : resolve(message.result);
  } else if (message.method && events.has(message.method)) {
    for (const callback of events.get(message.method)) callback(message.params);
  }
});
function command(method, params = {}) {
  const id = nextId++;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}
function once(method) {
  return new Promise((resolve) => {
    const callback = (params) => {
      events.set(method, (events.get(method) ?? []).filter((item) => item !== callback));
      resolve(params);
    };
    events.set(method, [...(events.get(method) ?? []), callback]);
  });
}
async function evaluate(expression) {
  const result = await command("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
}
async function navigate(url) {
  const loaded = once("Page.loadEventFired");
  await command("Page.navigate", { url });
  await Promise.race([loaded, new Promise((resolve) => setTimeout(resolve, 15000))]);
  await new Promise((resolve) => setTimeout(resolve, 350));
}
async function capture(path, width, viewportHeight, mobile) {
  const metrics = await command("Page.getLayoutMetrics");
  const height = Math.ceil(metrics.cssContentSize.height);
  await command("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile });
  await new Promise((resolve) => setTimeout(resolve, 900));
  const screenshot = await command("Page.captureScreenshot", { format: "png", fromSurface: true });
  await writeFile(path, Buffer.from(screenshot.data, "base64"));
  await command("Emulation.setDeviceMetricsOverride", { width, height: viewportHeight, deviceScaleFactor: 1, mobile });
  return height;
}
async function revealScrolledSections(viewportHeight) {
  await evaluate(`(async () => {
    const step = Math.max(360, Math.floor(window.innerHeight * 0.72));
    for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await new Promise(resolve => setTimeout(resolve, 65));
    }
    window.scrollTo(0, 0);
    await new Promise(resolve => setTimeout(resolve, 850));
    return document.documentElement.scrollHeight;
  })()`);
}

await command("Page.enable");
await command("Network.enable");
await command("Network.setCacheDisabled", { cacheDisabled: true });
await command("Runtime.enable");
await command("DOM.enable");
await command("CSS.enable");
const reports = [];
for (const theme of themes) {
  for (const viewport of viewports) {
    await command("Emulation.setDeviceMetricsOverride", {
      width: viewport.width, height: viewport.height, deviceScaleFactor: 1, mobile: viewport.width <= 430,
    });
    await command("Emulation.setTouchEmulationEnabled", { enabled: viewport.width <= 430, maxTouchPoints: 1 });
    if (theme.preference === "system") {
      await command("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme.colorScheme }] });
    } else {
      await command("Emulation.setEmulatedMedia", { features: [] });
    }
    await navigate(origin);
    await evaluate(`localStorage.setItem("paperloop.theme", ${JSON.stringify(theme.preference)})`);
    await navigate(origin);
    await revealScrolledSections(viewport.height);
    const sample = await evaluate(`(() => {
      const color = (el) => getComputedStyle(el).color;
      const bg = (el) => { for (let node=el; node && node !== document.documentElement; node=node.parentElement) { const s=getComputedStyle(node); if (s.backgroundImage !== "none") return { color:s.backgroundColor, image:s.backgroundImage, selector:node.className || node.tagName.toLowerCase() }; if (Number.parseFloat(s.backgroundColor.split(",")[3] ?? "1") > 0 || !s.backgroundColor.includes("0)")) return {color:s.backgroundColor,image:"none",selector:node.className || node.tagName.toLowerCase()}; } return {color:getComputedStyle(document.body).backgroundColor,image:"none",selector:"body"}; };
      const visible = (el) => { const r=el.getBoundingClientRect(),s=getComputedStyle(el); return r.width>0&&r.height>0&&s.display!=="none"&&s.visibility!=="hidden"&&Number(s.opacity)>0; };
      const headings=[...document.querySelectorAll("h1,h2,h3,h4,h5,h6,.landing-eyebrow,.about-eyebrow")].filter(visible).map(el=>({tag:el.tagName.toLowerCase(),text:(el.innerText||el.textContent).trim().replace(/\\s+/g," ").slice(0,110),color:color(el),surface:bg(el),fontFamily:getComputedStyle(el).fontFamily,fontSize:getComputedStyle(el).fontSize,fontWeight:getComputedStyle(el).fontWeight,lineHeight:getComputedStyle(el).lineHeight,opacity:getComputedStyle(el).opacity,rect:(()=>{const r=el.getBoundingClientRect();return {x:Math.round(r.x),y:Math.round(r.y),width:Math.round(r.width),height:Math.round(r.height)}})()}));
      const text=[...document.querySelectorAll("p,li,a,button,small,.footer-column-title,.pl-theme-current-label")].filter(visible).map(el=>({tag:el.tagName.toLowerCase(),text:(el.innerText||el.textContent).trim().replace(/\\s+/g," ").slice(0,100),color:color(el),surface:bg(el),fontFamily:getComputedStyle(el).fontFamily,fontSize:getComputedStyle(el).fontSize,opacity:getComputedStyle(el).opacity}));
      const sections=[...document.querySelectorAll("main section,main > div,footer")].filter(visible).map(el=>({selector:el.className || el.tagName.toLowerCase(),background:getComputedStyle(el).backgroundColor,image:getComputedStyle(el).backgroundImage,height:Math.round(el.getBoundingClientRect().height)}));
      const featureCards=[...document.querySelectorAll(".feature-editorial")].map(el=>({title:el.querySelector("h3")?.innerText,background:getComputedStyle(el).backgroundColor,border:getComputedStyle(el).borderColor,foreground:getComputedStyle(el.querySelector("h3")).color,description:getComputedStyle(el.querySelector("p")).color,index:getComputedStyle(el.querySelector(".feature-index")).color,iconColor:getComputedStyle(el.querySelector(".feature-editorial-icon")).color,iconBackground:getComputedStyle(el.querySelector(".feature-editorial-icon")).backgroundColor,watermark:getComputedStyle(el.querySelector(".feature-watermark")).color,watermarkOpacity:getComputedStyle(el.querySelector(".feature-watermark")).opacity,link:getComputedStyle(el.querySelector(".feature-link")).color}));
      const flowBoard=document.querySelector(".ecosystem-board"),flowCenter=document.querySelector(".ecosystem-center-node");
      const flowCards=[...document.querySelectorAll(".ecosystem-node")].map(el=>({title:el.querySelector("strong")?.innerText,background:getComputedStyle(el).backgroundColor,foreground:getComputedStyle(el).color,heading:getComputedStyle(el.querySelector("strong")).color,description:getComputedStyle(el.querySelector("div > span")).color,label:getComputedStyle(el.querySelector("small")).color,iconColor:getComputedStyle(el.querySelector(".node-icon")).color,iconBackground:getComputedStyle(el.querySelector(".node-icon")).backgroundColor}));
      const processTrack=document.querySelector(".process-track");
      const box=(el,base)=>{const a=el.getBoundingClientRect(),b=base.getBoundingClientRect();return {x:Math.round(a.x-b.x),y:Math.round(a.y-b.y),width:Math.round(a.width),height:Math.round(a.height)}};
      const processSteps=[...document.querySelectorAll(".process-track .process-step")].map(el=>({card:box(el,processTrack),background:getComputedStyle(el).backgroundColor,border:getComputedStyle(el).borderColor,borderRadius:getComputedStyle(el).borderRadius,icon:box(el.querySelector(".process-step-icon"),el),iconColor:getComputedStyle(el.querySelector(".process-step-icon")).color,iconBackground:getComputedStyle(el.querySelector(".process-step-icon")).backgroundColor,number:box(el.querySelector(".process-step-no"),el),numberColor:getComputedStyle(el.querySelector(".process-step-no")).color,heading:box(el.querySelector("h3"),el),headingText:el.querySelector("h3").innerText,headingColor:getComputedStyle(el.querySelector("h3")).color,description:box(el.querySelector("p"),el),descriptionText:el.querySelector("p").innerText,descriptionColor:getComputedStyle(el.querySelector("p")).color,headingOverflow:el.querySelector("h3").scrollWidth>el.querySelector("h3").clientWidth,descriptionOverflow:el.querySelector("p").scrollWidth>el.querySelector("p").clientWidth}));
      const processFlow=processTrack?{gridColumns:getComputedStyle(processTrack).gridTemplateColumns,gap:getComputedStyle(processTrack).gap,connectorColor:getComputedStyle(processTrack,"::before").backgroundColor,connectorMask:getComputedStyle(processTrack,"::before").maskImage,steps:processSteps}:null;
      const preview=document.querySelector(".ai-preview-window"),previewHeading=preview?.querySelector("h3");
      const toggleLabel=document.querySelector(".mobile-nav-toggle .visually-hidden");
      const feature=document.querySelector(".feature-editorial-forest");
      const featureRules=[...document.styleSheets].flatMap(sheet=>{try{return [...sheet.cssRules].filter(rule=>rule.selectorText?.includes("feature-editorial-grid .feature-editorial-forest")).map(rule=>rule.cssText)}catch{return []}});
      const switcherOptions=[...document.querySelectorAll("[data-theme-option]")].map(el=>({theme:el.dataset.themeOption,label:el.innerText.trim(),pressed:el.getAttribute("aria-pressed"),color:color(el),background:getComputedStyle(el).backgroundColor,iconColor:color(el.querySelector(".pl-icon"))}));
      return {effectiveTheme:document.documentElement.dataset.theme,preference:document.documentElement.dataset.themePreference,title:document.title,bodyClass:document.body.className,themeStylesheet:[...document.styleSheets].map(sheet=>sheet.href).find(href=>href?.includes("paperloop-themes")),selectedThemeLabel:document.querySelector("[data-theme-current]")?.textContent,themeMenu:getComputedStyle(document.querySelector("[data-theme-options]")).backgroundColor,headings,text,sections,links:[...document.querySelectorAll(".site-header nav a")].filter(visible).map(el=>({text:el.innerText,color:color(el),background:bg(el),current:el.getAttribute("aria-current")})),switcherOptions,featureCards,featureMatch:feature?{class:feature.className,matches:feature.matches("body.landing-page .feature-editorial-grid .feature-editorial-forest"),computedBackground:getComputedStyle(feature).backgroundColor,backgroundImage:getComputedStyle(feature).backgroundImage,footerBackground:getComputedStyle(feature).getPropertyValue("--pl-footer-bg"),inlineStyle:feature.getAttribute("style")}:null,featureRules,processFlow,paperFlow:flowBoard&&flowCenter?{boardBackground:getComputedStyle(flowBoard).backgroundColor,boardBackgroundImage:getComputedStyle(flowBoard).backgroundImage,boardBorder:getComputedStyle(flowBoard).borderColor,pattern:getComputedStyle(flowBoard.querySelector(".ecosystem-board-pattern")).backgroundImage,ring:getComputedStyle(flowBoard.querySelector(".ecosystem-ring")).borderColor,connector:getComputedStyle(flowBoard.querySelector(".ecosystem-connectors")).color,centerBackground:getComputedStyle(flowCenter).backgroundColor,centerForeground:getComputedStyle(flowCenter).color,centerLabel:flowCenter.querySelector("strong")?.innerText,cards:flowCards}:null,aiPreview:preview&&previewHeading?{background:getComputedStyle(preview).backgroundColor,heading:color(previewHeading),headingText:previewHeading.innerText}:null,mobileToggle:toggleLabel?{labelText:toggleLabel.innerText,position:getComputedStyle(toggleLabel).position,clip:getComputedStyle(toggleLabel).clip}:null};
    })()`);
    const documentNode = await command("DOM.getDocument", { depth: -1 });
    const featureNode = await command("DOM.querySelector", { nodeId: documentNode.root.nodeId, selector: ".feature-editorial-forest" });
    if (featureNode.nodeId) {
      const matched = await command("CSS.getMatchedStylesForNode", { nodeId: featureNode.nodeId });
      sample.featureMatchedRules = (matched.matchedCSSRules ?? []).map(({ rule }) => ({
        selector: rule.selectorList?.text,
        properties: (rule.style?.cssProperties ?? []).filter(({ name }) => ["background", "background-color", "color", "border-color"].includes(name)),
      }));
    }
    const shotName = `${theme.name}-${viewport.name}.png`;
    const height = await capture(`${outputDir}/${shotName}`, viewport.width, viewport.height, viewport.width <= 430);
    reports.push({ theme: theme.name, viewport: viewport.name, width: viewport.width, height, screenshot: shotName, ...sample });
    if (viewport.name === "mobile") {
      const mobileNavigation = await evaluate(`(() => { const toggle=document.querySelector("[data-mobile-nav-toggle]"); toggle.click(); const nav=document.getElementById(toggle.getAttribute("aria-controls")); const trigger=nav.querySelector("[data-theme-toggle]"); const options=nav.querySelector("[data-theme-options]"); return {expanded:toggle.getAttribute("aria-expanded"),menuDisplay:getComputedStyle(nav).display,themeLabel:nav.querySelector("[data-theme-current]")?.textContent,triggerColor:getComputedStyle(trigger).color,optionSurface:getComputedStyle(options).backgroundColor,optionText:getComputedStyle(options.querySelector("[data-theme-option]")).color}; })()`);
      const optionNode = await command("DOM.querySelector", { nodeId: documentNode.root.nodeId, selector: '.pl-theme-option[data-theme-option="dark"]' });
      if (optionNode.nodeId) {
        await command("CSS.forcePseudoState", { nodeId: optionNode.nodeId, forcedPseudoClasses: ["hover"] });
        mobileNavigation.optionHoverBackground = await evaluate(`getComputedStyle(document.querySelector('.pl-theme-option[data-theme-option="dark"]')).backgroundColor`);
        await command("CSS.forcePseudoState", { nodeId: optionNode.nodeId, forcedPseudoClasses: ["focus-visible"] });
        mobileNavigation.optionFocusOutline = await evaluate(`getComputedStyle(document.querySelector('.pl-theme-option[data-theme-option="dark"]')).outlineStyle`);
        await command("CSS.forcePseudoState", { nodeId: optionNode.nodeId, forcedPseudoClasses: [] });
      }
      await new Promise((resolve) => setTimeout(resolve, 120));
      const menuShot = await command("Page.captureScreenshot", { format: "png", fromSurface: true });
      await writeFile(`${outputDir}/${theme.name}-mobile-menu.png`, Buffer.from(menuShot.data, "base64"));
      reports.at(-1).mobileNavigation = mobileNavigation;
      await evaluate(`document.querySelector("[data-mobile-nav-toggle]").click()`);
    }
    if (theme.name === "light" && viewport.name === "desktop") {
      const sequence = [];
      for (const preference of ["dark", "forest", "system", "light", "dark"]) {
        await evaluate(`(() => { const toggle=document.querySelector("[data-theme-toggle]"); if (toggle.getAttribute("aria-expanded") !== "true") toggle.click(); document.querySelector('[data-theme-option="${preference}"]').click(); return document.documentElement.dataset.themePreference + ":" + document.documentElement.dataset.theme; })()`)
          .then((value) => sequence.push(value));
      }
      await navigate(origin);
      const persistedAfterRefresh = await evaluate(`document.documentElement.dataset.themePreference + ":" + document.documentElement.dataset.theme`);
      reports.at(-1).themeSequence = { sequence, persistedAfterRefresh };
    }
    console.log(`${theme.name} ${viewport.name}: ${viewport.width}x${height} theme=${sample.effectiveTheme}`);
  }
}
await writeFile(`${outputDir}/computed-styles.json`, JSON.stringify({ url: origin, reports }, null, 2));
socket.close();
