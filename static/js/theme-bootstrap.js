(function () {
	var THEME_STORAGE_KEY = 'knot-dark-mode';
	var enabled = false;

	try {
		enabled = localStorage.getItem(THEME_STORAGE_KEY) === '1';
	} catch (error) {
		enabled = false;
	}

	if (enabled) {
		document.documentElement.classList.add('dark-mode-init');
		document.documentElement.style.colorScheme = 'dark';
	}
})();