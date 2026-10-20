# PyPI release handoff

The package is not published yet. The confirmed company PyPI account is `mailchannels`;
a named operator and publishing access still need configuration. No token or live-provider
credential is needed for the build workflow. Its tests intercept HTTP and send no email.

## Configure once, before enabling uploads

1. Review and merge `.github/workflows/release.yml` and its guard tests.
2. In GitHub repository Settings → Environments, create `pypi`, assign the authorized
   release reviewer(s), and restrict deployment branches to `main`. Review any available
   bypass settings. Do this before enabling publishing; an unprotected environment name
   alone is not an approval gate.
3. Sign in to PyPI as the authorized operator for the company account `mailchannels`.
   Check whether `langchain-mailchannels` already exists. For a new project use
   https://pypi.org/manage/account/publishing/ to register a pending trusted publisher;
   for an existing company-owned project use its Publishing settings. Enter exactly:

   | Field | Value |
   | --- | --- |
   | PyPI project | `langchain-mailchannels` |
   | GitHub owner | `mailchannels` |
   | GitHub repository | `langchain-mailchannels` |
   | Workflow filename | `release.yml` |
   | Environment | `pypi` |

   A pending publisher does not reserve a name or prove a package was published. Do not
   use an unrelated personal PyPI account to bypass company ownership.
4. After verifying the environment restrictions and PyPI identity, set repository Actions
   variable `PYPI_PUBLISHING_ENABLED` to `true`. No persistent PyPI token is required.
   Leaving this unset keeps the upload job disabled even if `publish` is selected.

## Prepare a release

Use Actions → Prepare or publish Python release on `main` with `publish` unchecked.
A blank tag builds the current candidate. For a tagged candidate, use a stable tag such
as `v0.1.0` pointing at the reviewed commit already on `main`; its version must equal
`pyproject.toml`. Prerelease tag syntax is not supported by this initial guard.

The workflow tests the release guards, selects the validated source, runs package tests,
builds wheel/sdist, runs strict Twine metadata checks, and imports the installed wheel
outside the checkout. Download `python-distributions` and `release-report`; review the
commit/version in `release-info.json` and the file hashes in `SHA256SUMS`. Inspect the
archive contents and license. A successful candidate run does not publish anything.

Before the first release, complete separately authorized live provider dry-run validation
using the intended application-controlled sender/recipient configuration. The existing
GitHub Action dry-run permission does not extend to this package. Keep keys out of logs,
issues and chat. Record a sanitized result in the release review.

## Publish and verify

Dispatch from `main` with the reviewed tag and `publish` checked. The workflow rebuilds
and rechecks that tag; inspect this run's artifacts/report before approving its `pypi`
environment job. Checksums may differ between builds, so review the actual publishing
run, not only an earlier candidate run. Only the publisher job receives OIDC permission;
it downloads this run's distributions and uses PyPA's pinned publishing action with
attestations. It does not check out or execute package source. No automatic retry or
skip-existing setting is enabled; investigate partial upload errors before another run.

Verify the actual upload job succeeded (not merely that the overall workflow is green),
then verify https://pypi.org/project/langchain-mailchannels/ for the expected version,
owner, source links, files and attestations. Install the exact version in a clean environment
and exercise the intercepted-HTTP tests. Update README installation instructions and the
matching GitHub release only after registry verification. A tag or uploaded GitHub artifact
alone is not a PyPI release. Afterward, file LangChain's Integration listing issue form
(https://github.com/langchain-ai/docs/issues/new?template=06-integration-submission.yml);
manual docs PRs are auto-closed. Verify its public catalog page separately.

References:
- https://docs.pypi.org/trusted-publishers/adding-a-publisher/
- https://docs.pypi.org/trusted-publishers/using-a-publisher/
