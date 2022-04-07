# Changelog

## 3.1.1

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