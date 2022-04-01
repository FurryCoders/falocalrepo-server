# Changelog

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