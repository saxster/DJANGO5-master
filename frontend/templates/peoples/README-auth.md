# IntelliWiz Authentication Layout

This directory uses a shared `auth_base.html` template and associated static assets to deliver a consistent, enterprise-grade experience across login-adjacent pages.

## Templates

- `auth_base.html` – shared shell that renders the centered authentication card, brand header, and footer. Provides the following blocks:
  - `title` – set the document title.
  - `brand` – logo and product identity region.
  - `content` – primary body of the card.
  - `extra_head` – inject page-specific `<head>` markup.
  - `extra_scripts` – append scripts after the shared bundle.
  - `footer` – override if custom footer messaging is needed.
- `login.html` – IntelliWiz corporate sign-in experience.
- `nosite.html` – site selection screen for users without a default assignment.

## Static assets

Shared styles, interactions, and brand assets are located under `frontend/static/`:

- `auth/intelliwiz_auth.css` – design tokens, layout rules, and component classes for the authentication shell.
- `auth/intelliwiz_auth.js` – lightweight enhancements (password visibility toggle, submit loading state).
- `assets/media/logos/youtility_technologies_logo.svg` – preferred logo artwork for IntelliWiz/Youtility branding.

Include the stylesheet and script through `{% static %}` as shown in `auth_base.html`. Additional form-specific assets should be inserted via the `extra_head` and `extra_scripts` blocks to avoid duplication.

## Usage guidelines

1. Extend `peoples/auth_base.html` for any new authentication or session-oriented page.
2. Supply the shared branding context in the view (`product_name`, `company_name`, `tagline`, `support_contact`, `env_hostname`, `current_year`). See `SignIn` and `NoSite` views for reference.
3. Apply the `.auth-input` or `.auth-select` classes to controls to inherit spacing and focus treatments. Use `.auth-button` for primary actions and `.auth-link-button` for secondary ones.
4. Keep backgrounds solid (no gradients) and apply the IntelliWiz palette:
   - Youtility Blue `#0672B6` (primary actions)
   - Corporate Navy `#0A1A2F` (primary text)
   - Slate Gray `#4E6079` (muted text and icons)
   - Accent Cyan `#4AC0F1` (supporting highlights)
   - Neutral Light Gray `#F2F3F5` (page background)
5. Use Inter for headings (Bold/SemiBold) and Roboto for body/interface copy (Regular/Medium) as loaded in `auth_base.html`.
6. Ensure new templates provide accessible labels, help text IDs, and consistent error placement.

Following these guidelines keeps every auth-related surface consistent with the IntelliWiz enterprise aesthetic.
