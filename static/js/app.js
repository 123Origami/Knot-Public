// Global app behaviors shared across member pages.
(function () {
	var THEME_STORAGE_KEY = 'knot-dark-mode';

	function readThemePreference() {
		try {
			return localStorage.getItem(THEME_STORAGE_KEY) === '1';
		} catch (error) {
			return false;
		}
	}

	function persistThemePreference(enabled) {
		try {
			localStorage.setItem(THEME_STORAGE_KEY, enabled ? '1' : '0');
		} catch (error) {
			// Ignore storage failures (private mode or storage restrictions).
		}
	}

	function applyTheme(enabled) {
		document.body.classList.toggle('dark-mode', enabled);
		document.documentElement.classList.toggle('dark-mode-init', enabled);

		var toggle = document.getElementById('darkModeToggle');
		if (toggle) {
			toggle.checked = enabled;
		}
	}

	function initThemeToggle() {
		var toggle = document.getElementById('darkModeToggle');
		if (!toggle || toggle.dataset.themeBound === '1') {
			return;
		}

		toggle.addEventListener('change', function () {
			var enabled = !!toggle.checked;
			persistThemePreference(enabled);
			applyTheme(enabled);
		});

		toggle.dataset.themeBound = '1';
	}

	function initUserDropdown() {
		var dropdowns = document.querySelectorAll('.user-dropdown');
		if (!dropdowns.length) {
			return;
		}

		function closeAllDropdowns(exceptDropdown) {
			dropdowns.forEach(function (dropdown) {
				if (dropdown !== exceptDropdown) {
					dropdown.classList.remove('open');
				}
			});
		}

		dropdowns.forEach(function (dropdown) {
			if (dropdown.dataset.dropdownBound === '1') {
				return;
			}

			dropdown.addEventListener('click', function (event) {
				if (event.target.closest('.dropdown-menu')) {
					return;
				}

				event.preventDefault();
				event.stopPropagation();

				var shouldOpen = !dropdown.classList.contains('open');
				closeAllDropdowns(dropdown);
				dropdown.classList.toggle('open', shouldOpen);
			});

			dropdown.dataset.dropdownBound = '1';
		});

		document.addEventListener('click', function () {
			closeAllDropdowns(null);
		});
	}

	// Apply theme immediately to prevent flash
	applyTheme(readThemePreference());

	document.addEventListener('DOMContentLoaded', function () {
		initThemeToggle();
		initUserDropdown();
	});
})();
