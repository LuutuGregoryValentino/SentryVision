const fs = require("fs");
const path = require("path");
const vm = require("vm");

const RESULT_MARKER = "@@SENTRY_VISION_RESULT@@";
const [browserDir, featuresPath] = process.argv.slice(2);

if (!browserDir || !featuresPath) {
    console.error("Usage: node edge_impulse_runner.js <browser-dir> <features-json>");
    process.exit(2);
}

const resolvedBrowserDir = path.resolve(browserDir);
const context = {
    console,
    process,
    require,
    __dirname: resolvedBrowserDir,
    __filename: __filename,
    setTimeout,
    clearTimeout,
    Module: {
        locateFile: (filename) => path.join(resolvedBrowserDir, filename),
    },
};

context.global = context;
context.globalThis = context;
vm.createContext(context);

vm.runInContext(
    fs.readFileSync(path.join(resolvedBrowserDir, "edge-impulse-standalone.js"), "utf8"),
    context,
    { filename: "edge-impulse-standalone.js" },
);
vm.runInContext(
    fs.readFileSync(path.join(resolvedBrowserDir, "run-impulse.js"), "utf8")
        + "\nglobal.EdgeImpulseClassifier = EdgeImpulseClassifier;",
    context,
    { filename: "run-impulse.js" },
);

const features = JSON.parse(fs.readFileSync(featuresPath, "utf8"));
context.features = features;

vm.runInContext(`
(async () => {
    const classifier = new global.EdgeImpulseClassifier();
    await classifier.init();
    const properties = classifier.getProperties();
    const result = classifier.classify(global.features);
    console.log("${RESULT_MARKER}" + JSON.stringify({ properties, result }));
})().catch((error) => {
    console.error(error && error.stack ? error.stack : error);
    process.exit(1);
});
`, context);
