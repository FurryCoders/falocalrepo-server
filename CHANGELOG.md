# Changelog

## v3.2.2

### New Features

* Open browser on startup 💻
    * A new browser tab with the running app is opened automatically when the programs starts
    * New `--browser` and `--no-browser` options to toggle opening the browser (defaults on)

### Changes

* Improved handling of spoiler text

### Fixes

* Fix [CVE-2022-30595](https://github.com/advisories/GHSA-hr8g-f6r6-mr22) and
  solve [security issue 1](https://github.com/FurryCoders/falocalrepo-server/security/dependabot/1)
* Fix journals searches
* Fix rounded corners for overlaid submission images not behaving correctly when scrolling on mobile

## v3.2.1

### New Features

* Add file counter in search results for submissions with more than one submission file

## v3.2.0

### New Features

* Support multiple submission files files 🗂
    * New file switcher to select the submission file to view
    * New route to download multiple submission files as a ZIP
* Support video files 📼
    * Show MP4, WebM, and OGG files directly in the browser

### Changes

* Show thumbnail when no main file is available for a submission
* The `@any` query field does not include `FAVORITES`, `FILESAVED`, `USERUPDATE`, nor `ACTIVE` to avoid redundant
  results
* The `@author` field matches submissions that contain the query value instead of finding only exact matches (i.e. `ab`
  matches `cabd`, `abcd`, etc.)
* Removed loading cursor and behaviour to avoid problems when opening links in new tabs/windows

### Fixes

* Fix rounded borders of submission files triggering incorrectly on mobile while scrolling

### Dependencies

* Use [falocalrepo-database ~5.3.0](https://pypi.org/project/falocalrepo-database/5.3.0)

## v3.1.4

### New Features

* Navbar
    * A persistent navbar with links to the home screen, submissions, journals, and users searches
    * The navbar is not sticky and remains at the top of the page
* Last update badge on home screen
    * The date of the last event in the HISTORY table, or the modified time of the database file if there are no events
      saved

### Changes

* Setting the `page` query parameter for search URLs will show the last page if the page value is beyond the results of
  the search.

## v3.1.3

### New Features

* Floating button for comments
    * If a submission/journal has comments, a new floating button appears in the lower right corner of the screen to
      navigate directly to the comments

### Changes

* USERNAME is matched using `like` (i.e. when searching for users the results will be of users whose name contains the
  query string instead of being matched exactly)
* Journal content and user profiles are longer part of the metadata card on small screens
* Text submissions now show their thumbnail above the text
* When zooming an image submission, the metadata card is now moved to the right of the description
* Submissions and journals have a new metadata card with the total number of comments related to them
* Improved the style of submission image overlay
* When searching and saving settings, a wait cursor appears
* The submission thumbnail route now supports setting height and width separately

### Fixes

* Fix missing border around text submissions
* Fix list view links not covering the full height of the row
* Fix thumbnails that weren't loaded before moving to the next search page not loading when going back
* Fix submissions whose type is `flash` but used image files other than GIF not being displayed as images
* Fix rare infinite recursion error when processing comments

### Dependencies

* Use [falocalrepo-database ~5.2.2](https://pypi.org/project/falocalrepo-database/5.2.2)

## v3.1.2

### New Features

* Flash Player! ▶️
    * Playback of Flash files is now fully supported thanks to [Ruffle](https://ruffle.rs)
    * Ruffle is loaded via CDN to avoid making the package too heavy (Ruffle weighs around 6MB), so an internet
      connection is required to play Flash files

### Changes

* Improved layout when zooming on desktop screens
* Improved efficiency of submission pages
* Submission file is now placed above the metadata instead of inside the card on small screens
* Sticky image button is available on all devices

### Fixes

* Fix submissions that have type `flash` but use GIF files not being shown
* Fix buttons not being clickable if on the same line as the sticky image button
* Fix sticky image button not being drawn above zoomed sticky image

## v3.1.1

### Changes

* Using a database with a version number that differs only in patch will not trigger a `VersionError` exception

### Fixes

* Fix legacy emojis being rendered in italic and disregarding the style of the text around them

### Dependencies

* Use [falocalrepo-database ~5.2.1](https://pypi.org/project/falocalrepo-database/5.2.1)

## v3.1.0

### New Features

* Comments
    * Comments for submissions and journals are shown at the bottom of the respective page, with indentation for replies
* Submission image overlay
    * When viewing a submission with an image file on mobile, a new button appears in the lower right which when clicked
      puts the image into an overlay, so it can be seen when scrolling down to read the description
    * The overlaid image still supports tap-to-zoom
* Legacy Fur Affinity emojis
    * Full support for legacy emojis like `:veryhappy:`, `:love:`, etc. which are now rendered with modern emojis
    * No modern emoji exists for `:whatever:` and `:badhairday:` emojis, so `:3` and `:badhair:` are used instead to
      avoid empty tags

### Changes

* Submission images can fill the entire width of the window when enlarged on desktop

### Fixes

* Fix error which caused the pre-cache to be ignored

### Dependencies

* Use [falocalrepo-database ~5.2.0](https://pypi.org/project/falocalrepo-database/5.2.0)
* Use [fastapi ^0.75.1](https://pypi.org/project/fastapi/0.75.0)

## v3.0.5

### Changes

* When hovering above a submission image, the cursor changes depending on whether it is zoomed in or out

### Dependencies

* Use [click ^8.0.12](https://pypi.org/project/click/8.0.12)

## v3.0.4

### Fixes

* Fix precaching not performing correctly when the sorting was set to date

### Dependencies

* Use [fastapi ^0.75.0](https://pypi.org/project/fastapi/0.75.0)
* Use [uvicorn ^0.17.6](https://pypi.org/project/uvicorn/0.17.6)

## v3.0.3

### Fixes

* Fix error page not having the correct scale
* Fix sorting option shown as ID when set to date

## v3.0.2

### New Features

* Click on the submission image to enlarge it
* Loading animation for image files

### Changes

* Improved margins
* Set default sorting of submissions and journals to date
    * The backend uses ID for faster and more precise results

### Fixes

* Fix crashes due to incorrectly encoded text submissions files

## v3.0.1

### New Features

* Support for Fur Affinity search queries and links
    * All search fields are supported
    * URL parameters used by Fur Affinity are automatically converted
    * The not (!) operator is not supported as it behaves differently

### Changes

* The view option can be changed live, without having to run search again
* Improved the search help icon
* The FILESAVED, USERUPDATE, and ACTIVE search fields are matched without expansions (i.e. if the query value is _1_, it
  will be matched only with entries with a value exactly equal to _1_ instead of containing _1_)
    * LIKE expansion can be toggled manually with the `_` and `%` operators

### Fixes

* Fix query field not being filled when loading a search page
* Fix error when sorting by relevance

## v3.0.0

### New Features

* Full rewrite with Bootstrap
    * Completely new UI using [Bootstrap](https://getbootstrap.com) for a responsive, modern interface
    * Javascript usage has been almost completely eliminated for a much faster experience and lighter load
    * Search settings can now be customized for each table and saved in the database
    * Search results can be viewed in both list and card (with thumbnails for submissions) mode for all tables and
      device sizes

### Changes

* HTML content is cleaned up before serving to avoid unnecessary external requests, and to avoid using Javascript after
  load
* All responses are minified
* Database files from non-writable locations are supported
* Next/prev buttons are supported in user pages as well

### Fixes

* Fix some routes not providing automatic redirection for missing trailing slashes

### Dependencies

* Use [falocalrepo-database ~5.1.2](https://pypi.org/project/falocalrepo-database/5.1.2)
* Use [beautifulsoup4 ^4.10.0](https://pypi.org/project/beautifulsoup4/4.10.0)
* Use [lxml ^4.8.0](https://pypi.org/project/lxml/4.8.0)
* Use [htmlmin ^0.1.12](https://pypi.org/project/htmlmin/0.1.12)