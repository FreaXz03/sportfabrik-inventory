#!/bin/sh
# Install only pre-push; preserve existing post-checkout/post-commit hooks.
set -eu
root=$(git rev-parse --show-toplevel)
hook=$(git rev-parse --git-path hooks/pre-push)
if [ -f "$hook" ] && ! cmp -s "$root/.githooks/pre-push" "$hook"; then
  cp "$hook" "$hook.before-sportfabrik-$(date +%Y%m%dT%H%M%S)"
fi
cp "$root/.githooks/pre-push" "$hook"
chmod 755 "$hook"
git config push.default simple
git config remote.origin.push refs/heads/working/entwicklung:refs/heads/working/entwicklung
printf '%s\n' 'Push guard installed; only working/entwicklung can be pushed.'
