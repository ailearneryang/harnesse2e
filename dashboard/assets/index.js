(function loadDashboardScripts() {
    const scripts = [
        '/assets/js/core.js',
        '/assets/js/navigation.js',
        '/assets/js/views.js',
        '/assets/js/runtime.js',
        '/assets/js/pipeline-editor.js',
    ];

    function loadScript(index) {
        if (index >= scripts.length) return;

        const script = document.createElement('script');
        script.src = scripts[index];
        script.async = false;
        script.onload = function () {
            loadScript(index + 1);
        };
        script.onerror = function () {
            console.error('[HARNESS] Failed to load script:', scripts[index]);
        };
        document.body.appendChild(script);
    }

    loadScript(0);
})();
