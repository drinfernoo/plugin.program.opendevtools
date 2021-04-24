# OpenDevTools

### About
This add-on allows you to download add-ons directly from GitHub, from any branch or any commit, including tags.
It is an advanced tool for developers, and it is highly recommended that the add-on be installed properly from a zip or repository first.


### Authorizing GitHub
This add-on requires authorization via GitHub's [OAuth API](https://docs.github.com/en/enterprise-server@3.0/developers/apps/authorizing-oauth-apps#directing-users-to-review-their-access), which can be done via the Settings menu.


### How to Add Repositories
Open the add-on and choose `Add Repository`. When prompted, enter the repository owner's username and repository name.
If the repository contains a valid Kodi add-on in its root folder, then the add-on's name and plugin ID will be found automatically.

**NOTE**: If the repository *does not* contain a valid add-on in it's root folder, then a warning will be shown. The tool will still attempt to
download such repositories, but they will likely not be functional inside Kodi.
