# Changelog

## v3.3.2

### New Features

* Grid view for submissions with multiple files 📱
    * New button added to the file switcher that toggles a grid view showing all the files for a submission, regardless
      of type
    * Flash files are not minimized because of the way they are drawn, making it impossible to have the size change
      responsively, a "SWF" tag is shown in their place instead

### Changes

* Add subtle animations and shadow effects to sticky files
* Improve loading animations and "not found" badges
* Update theme-color to match dark/light mode
    * Support dynamic toolbar tinting on browsers that support it
* Disable double-tap to zoom on mobile devices
    * Avoids issues with buttons on some browsers causing unintentional zoom
    * Pinch to zoom is still available
* Reduce height of non-expanded submission files on desktop
* Improve caching behaviour by storing reverse order in advance

### Fixes

* Fix user icons not showing up properly in submissions, journals, and user profiles
* Fix ruffle errors not showing up
    * Ruffle does not elevate its errors to the client so they cannot be caught and displayed in the like other errors
* Fix "Thumbnail not found" error badges overflowing

### Dependencies

* Use [bootstrap 5.2.2](https://blog.getbootstrap.com/2022/10/03/bootstrap-5-2-2/)
* Use [fastapi ^0.85.1](https://pypi.org/project/fastapi/0.85.1)

## v3.3.1

### Fixes

* Fix margins around horizontal bars in journal headers and footers
* Fix BBCode button appearing for journals even in HTML databases
* Fix uneven margins at the bottom of descriptions and journals
* Fix user icons not appearing when the server's timezone was too far ahead of Fur Affinity's

## v3.3.0

### New Features

* \[BBCode\]
    * Support BBCode databases introduced
      with [falocalrepo-database 5.4.0](https://pypi.org/project/falocalrepo-database/5.4.0)
      and [falocalrepo 4.4.0](https://pypi.org/project/falocalrepo/4.4.0)
    * Search is much more precise and does not return incorrect results (e.g. searching for "strong" would return all
      submissions that contained a `<strong>` tag)
    * **Note:** the BBCode to HTML conversion is still a work in progress and some submissions may not render correctly
      if they contain very unusual formatting, please open
      an [issue](https://github.com/FurryCoders/falocalrepo-server/issues) if you encounter any error :)
* User icons 🦊
    * User icons are now displayed like on Fur Affinity instead of being converted to @username links.
    * Icons are loaded from Fur Affinity and will not display if the client is not online
    * Icons are displayed in all HTML and BBCode elements, and will also show up in the users search page
* Journal headers and footers
    * Display headers and footers of journals if they are present in the database

### Changes

* Improved styling for quotes
* Improved styling for headers and footers
* Improved JSON responses
* Support BBCode icons in text submissions

### Fixes

* Fix galleries showing submissions from different users if their usernames was a substring of others'  (e.g. gallery
  for `ab` would also show submissions for `abc` and others)

### Dependencies

* Use [bootstrap 5.2.1](https://blog.getbootstrap.com/2022/09/07/bootstrap-5-2-1/)
* Use [falocalrepo-database ~5.4.0](https://pypi.org/project/falocalrepo-database/5.4.0)
* Use [fastapi ^0.84.0](https://pypi.org/project/fastapi/0.84.0)
* Use [uvicorn ^0.18.3](https://pypi.org/project/uvicorn/0.18.3)
* Use [jinja2 ^3.1.2](https://pypi.org/project/jinja2/3.1.2)
* Use [click ^8.1.3](https://pypi.org/project/click/8.1.3)
* Use [beautifulsoup4 ^4.11.1](https://pypi.org/project/beautifulsoup4/4.11.1)
* Add [bbcode ^1.1.0](https://pypi.org/project/bbcode/1.1.0)

## v3.2.9

### New Features

* Original legacy Fur Affinity emojis ❤️
    * Furaffinity emojis, like `:love:` and `:veryhappy:` are now rendered with the same sprites used in Fur Affinity

  ![](https://github.com/FurryCoders/falocalrepo-server/raw/main/falocalrepo_server/static/styles/sprite_smilies.png)

  _Full credits for the sprites goes to Fur Affinity_

### Fixes

* Fix last page button in search pages

### Dependencies

* Use [fastapi ^0.79.0](https://pypi.org/project/fastapi/0.79.0)
    * Was incorrectly set to =0.79.0 in version v3.2.8

## v3.2.8

### New Features

* Light & Dark mode toggle ☀️🌙
    * A new button in the navbar allows to manually toggle between light and dark mode
    * Changing your system's light/dark mode setting will override the currently selected option until the toggle is
      pressed again
* Boostrap 5.2.0
    * The Bootstrap library has been updated to
      its [latest stable version](https://blog.getbootstrap.com/2022/07/19/bootstrap-5-2-0/)

### Changes

* Cache is cleared automatically when the database changes to keep memory usage low

### Dependencies

* Use [fastapi ^0.79.0](https://pypi.org/project/fastapi/0.79.0)

## v3.2.7

### Dependencies

* Use [lxml ^4.9.1](https://pypi.org/project/lxml/4.9.1)
    * Fix [CVE-2022-2309](https://cve.report/CVE-2022-2309.pdf) issue
* Use [falocalrepo-database ~5.3.7](https://pypi.org/project/falocalrepo-database/5.3.7)
* Use [uvicorn ^0.18.2](https://pypi.org/project/uvicorn/0.18.2)
* Use [chardet ^5.0.0](https://pypi.org/project/chardet/5.0.0)
* Use [Pillow ^9.2.0](https://pypi.org/project/Pillow/9.2.0)

## v3.2.6

### Changes

* Text files are rendered without adding paragraphs for each new line, representing them closer to how they are
* Add support for various tags to text files:
    * Horizontal rules (5 or more of `-` or `=`)
    * Prev, first, next links for submissions (e.g., `[2,1,3]`)
    * `:linkusername:` and `@username`
    * `(c)`, `(tm)`, and `(r)`

### Fixes

* Fix missing logging

## v3.2.5

### Changes

* Thumbnail size is reduced for audio, text, and general files
* Improved formatting of text files

### Fixes

* Fix text files not appearing if they were not the first in the index

### Dependencies

* Use [falocalrepo-database ~5.3.5](https://pypi.org/project/falocalrepo-database/5.3.5)
* Use [uvicorn ^0.18.1](https://pypi.org/project/uvicorn/0.18.1)

## v3.2.4

### Changes

* Ruffle player pauses if the file is changed

### Fixes

* Fix width of Ruffle player

## v3.2.3

### Changes

* Removed `--browser` option as it duplicated the default behaviour
    * The `--no-browser` option remains and disables opening the browser automatically

### Fixes

* Fix rounded corners for overlaid submission images and videos
* Fix Ruffle being loaded when not necessary
* Fix missing legacy icons rendering

## v3.2.2

### New Features

* Open browser on startup 💻
    * A new browser tab with the running app is opened automatically when the program starts
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

* Support multiple submission files 🗂
    * New file switcher to select the submission file to view
    * New route to download multiple submission files as a ZIP
* Support video files 📼
    * Show MP4, WebM, and OGG files directly in the browser
* Boostrap 5.2.0 beta 1
    * The Bootstrap library has been updated to
      its [newest beta version](https://blog.getbootstrap.com/2022/05/13/bootstrap-5-2-0-beta/)

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