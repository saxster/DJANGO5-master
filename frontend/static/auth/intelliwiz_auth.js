document.addEventListener('DOMContentLoaded', () => {
    const passwordToggle = document.querySelector('[data-password-toggle]');
    const passwordInput = document.querySelector('[data-password-input]');
    const form = document.querySelector('[data-auth-form]');
    const submitButton = form ? form.querySelector('[data-auth-submit]') : null;
    const buttonLabel = submitButton ? submitButton.querySelector('.auth-button__label') : null;

    if (passwordToggle && passwordInput) {
        passwordToggle.addEventListener('click', () => {
            const isPassword = passwordInput.getAttribute('type') === 'password';
            passwordInput.setAttribute('type', isPassword ? 'text' : 'password');
            passwordToggle.setAttribute('aria-pressed', String(isPassword));
            passwordToggle.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');

            const showIcon = passwordToggle.querySelector('[data-icon="show"]');
            const hideIcon = passwordToggle.querySelector('[data-icon="hide"]');
            if (showIcon && hideIcon) {
                showIcon.hidden = !isPassword;
                hideIcon.hidden = isPassword;
            }

            if (isPassword) {
                passwordInput.focus();
            }
        });
    }

    if (form && submitButton && buttonLabel) {
        form.addEventListener('submit', () => {
            if (submitButton.classList.contains('is-loading')) {
                return;
            }

            submitButton.classList.add('is-loading');
            submitButton.disabled = true;

            const defaultLabel = buttonLabel.getAttribute('data-default-label') || buttonLabel.textContent;
            const loadingLabel = buttonLabel.getAttribute('data-loading-label');

            if (loadingLabel) {
                buttonLabel.textContent = loadingLabel;
                buttonLabel.setAttribute('data-default-label', defaultLabel || 'Sign in');
            }
        });
    }
});
