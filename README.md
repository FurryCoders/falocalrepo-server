# FALocalRepo-Server

[![version_pypi](https://img.shields.io/pypi/v/falocalrepo-server?logo=pypi)](https://pypi.org/project/falocalrepo-server/)
[![version_gitlab](https://img.shields.io/badge/dynamic/json?logo=gitlab&color=orange&label=gitlab&query=%24%5B%3A1%5D.name&url=https%3A%2F%2Fgitlab.com%2Fapi%2Fv4%2Fprojects%2Fmatteocampinoti94%252Ffalocalrepo-server%2Frepository%2Ftags)](https://gitlab.com/MatteoCampinoti94/falocalrepo-server)
[![version_python](https://img.shields.io/pypi/pyversions/falocalrepo-server?logo=Python)](https://www.python.org)

Web interface for [falocalrepo](https://pypi.org/project/falocalrepo/).

_Favicon by Fur Affinity._

## Installation & Requirements

To install the program it is sufficient to use Python pip and get the package `falocalrepo-server`.

```shell
python3 -m pip install falocalrepo-server
```

Python 3.9 or above is needed to run this program, all other dependencies are handled by pip during installation. For
information on how to install Python on your computer, refer to the official
website [Python.org](https://www.python.org/).

For the program to run, a properly formatted database created by falocalrepo needs to be present in the same folder.

## Usage

```
falocalrepo-server <database> [<host>:<port>]
```

The server needs one argument pointing at the location of a valid [falocalrepo](https://pypi.org/project/falocalrepo/)
database and accepts an optional argument to manually set host and port. By default, the server is run on 0.0.0.0:8080.

Once the server is running - it will display status messages in the terminal - the web app can be accessed
at http://0.0.0.0:8080/, or any manually set host/port combination.

_Note:_ All the following paths are meant as paths from `<host>:<port>`.

The root folder `/` displays basic information on the database and has links to perform submissions and journal
searches.

## Routes

|Route                                    |Destination|
|-----------------------------------------|---|
|`/`                                      | Show home page with general information regarding the database|
|`/browse/`                               | Redirects to `/browse/submissions/`|
|`/browse/submissions/`                   | Browse submissions|
|`/browse/journals/`                      | Browse journals|
|`/browse/users/`                         | Browse users|
|`/search/`                               | Redirects to `/search/submissions/`|
|`/search/submissions/`                   | Search submissions|
|`/search/journals/`                      | Search journals|
|`/search/users/`                         | Search users|
|`/user/<username>/`                      | Show information regarding a specific user|
|`/gallery/<username>/`                   | Browse a user's gallery submissions|
|`/scraps/<username>/`                    | Browse a user's scraps submissions|
|`/submissions/<username>/`               | Browse a user's gallery & scraps submissions| 
|`/favorites/<username>/`                 | Browse a user's favorite submissions|
|`/mentions/<username>/`                  | Browse the submissions where the user is mentioned|
|`/journals/<username>/`                  | Browse a user's journals|
|`/full/<submission id>/`                 | Redirect to `/submission/<submission id>/`|
|`/view/<submission id>/`                 | Redirect to `/submission/<submission id>/`|
|`/submission/<submission id>/`           | View a submission|
|`/submission/<submission id>/file/`      | Open a submission file|
|`/submission/<submission id>/thumbnail/` | Open a submission thumbnail (generated for image if no thumbnail is stored)|
|`/submission/<submission id>/zip/`       | Download a submission's file, description, and metadata as a ZIP archive|
|`/journal/<journal id>/`                 | View a journal|
|`/journal/<journal id>/zip/`             | Download a journal's content and metadata as a ZIP archive|

## Pages

### Home

The home page displays general information about the database and contains links to browse and search pages for the
various tables.

The information table displays the total number of submissions, journals, and users together with the version of the
database. Clicking on any of the counters open the relevant browse page.

Underneath the information table are buttons that open new search pages for submissions, journals, and users.

### Browse & Search

The browse and search pages allow to explore the submissions/journals contained in the database. Searches are performed
case-insensitively using a simple syntax in the form `@field term [[| &] term ...]` which allows logic operators,
parentheses and start/end of field matching, see [Query Language](#query-language) for details.

Search terms for submissions and journals default to the `any` field if none is used, while the `username` field is used
for users searches.

The controls at the top of the page allow to query the database and control the visualisation of the results.

![browse controls](https://gitlab.com/MatteoCampinoti94/falocalrepo-server/-/raw/master/doc/browse.png)

The _Search_ input allows to insert the search query.

The _Add Field_ menu allows to insert a specific search field using a simple dropdown menu.

The _-_ button clears the search input field.

The _Sort By_ and _Order_ menus change the sorting field and order of the search results. Submissions and journals
default to descending ID, while users default to ascending username.

The _View_ menu is only visible for submissions and allows changing between the (default) grid view to the list view
used for journals and users. Submission thumbnails are visualised in both cases.

The _Search_ button submits the search request using the current query and sorting settings.

Under the search controls are the number of results and current page.

Under the results numbers are the page controls. _First_ leads to page 1, _Prev_ leads to the previous page, _Next_
leads to the next page, and _Last_ leads to the last page. These controls are also available at the bottom of the page.

#### Query Language

The query language used for this server is based on and improves the search syntax currently used by the Fur Affinity
website. Its basic elements are:

* `@<field>` field specifier (e.g. `@title`), all database columns are available as search fields.
  See [falocalrepo-database](https://pypi.org/project/falocalrepo-database/) for details on the available columns.
* `()` parentheses, they can be used for better logic operations
* `&` _AND_ logic operator, used between search terms
* `|` _OR_ logic operator, used between search terms
* `!` _NOT_ logic operator, used as prefix of search terms
* `""` quotes, allow searching for literal strings without needing to escape
* `%` match 0 or more characters
* `_` match exactly 1 character
* `^` start of field, when used at the start of a search term, it matches the beginning of the field
* `$` end of field, when used at the end of a search term, it matches the end of the field

All other strings are considered search terms.

The search uses the `@any` field by default, allowing to do general searches without specifying a field.

Search terms that are not separated by a logic operator are considered _AND_ terms (i.e. `a b c` -> `a & b & c`).

Except for the `ID`, `AUTHOR`, and `USERNAME` fields, all search terms are searched through the whole content of the
various fields: i.e. `@description cat` will match any item whose description field contains "cat". To match items that
contain only "cat" (or start with, end with, etc.), the `%`, `_`, `^`, and `$` operators need to be used (
e.g. `@description ^cat`).

Search terms for `ID`, `AUTHOR`, and `USERNAME` are matched exactly as they are: i.e. `@author tom` will match only
items whose author field is exactly equal to "tom", to match items that contain "tom" the `%`, `_`, `^`, and `$`
operators need to be used (e.g. `@author %tom%`).

##### Examples

Search for journals/submissions containing water and either otter, lutrine, or mustelid, or water and either cat or
feline:

`water ((otter | lutrine | mustelid) | (cat | feline))`

`@any water & ((otter | lutrine | mustelid) | (cat | feline))`

Search for journals/submissions containing "cat" or "feline" but neither "mouse" nor "rodent":

`(cat | feline) !mouse !rodent`

Search for general-rated submissions uploaded by a user whose name starts with "tom" that contain either "volleyball"
or "volley" and "ball" separated by one character (e.g. "volley-ball") in any field:

`@rating general @author tom% @any (volleyball | volley_ball)`

`(volleyball | volley_ball) @rating general @author tom%`

Search for journals/submissions uploaded in 2020 except for March:

`@date ^2020 !^2020-03`

Search for submissions uploaded in March 2021 (meaning the date has to start with `2021-03`) whose tags contain the
exact tag "ball":

`@date ^2021-03 @tags "|ball|"`

`@date ^2021-03 @tags \|ball\|`

Search for journals/submissions where a specific user named "tom" is mentioned:

`@mentions "|tom|"`

`@mentions \|tom\|`

Search for submissions whose only favorite is a user named "alex":

`@favorite ^\|alex\|$`

Search for users whose names contain "mark":

`@username %mark%`

Search for journals/submissions whose title ends with "100%":

`@title 100\%$`

Search for journals/submissions whose title is exactly "cat":

`@title ^cat$`

Search for text submissions with PDF files:

`@type text @fileext pdf`

### User

The user page shows information about submissions and journals related to a user (gallery, scraps, favorites, mentions,
and journals) and what folders have been set for download. See [falocalrepo](https://pypi.org/project/falocalrepo/) for
more details on this.

Clicking on any of the counters opens the relevant results via the search interface, allowing to refine the search
further.

### Submission

The submission page shows the submission file (if present), the submission metadata, and the description.

Image, audio, and plain text submission files are displayed directly in the page, others (e.g. PDF files) will display a
link to open them. For images, clicking on the images opens its file.

The metadata table contains clickable links to the user's page (see [User](#user) for details), tags, category, species,
gender, rating, folder (gallery/scraps), and to user pages of favouring and mentioned users.

The description is displayed as-is except for user icons, which are replaced by `@username` styled links to avoid
display errors caused by expired icon links.

Under the metadata table are a number of buttons that allow to access the submission file, open its Fur Affinity
counterpart, and navigate the other submissions from the author.

![submission controls](https://gitlab.com/MatteoCampinoti94/falocalrepo-server/-/raw/master/doc/submission.png)

The _Download File_ button opens the submission file in the current browser tab.

The _Download Submission as ZIP_ button generates a ZIP file containing the submission file, submission thumbnail,
description HTML, and metadata in JSON format.

The _Open on Fur Affinity_ button opens the submission on Fur Affinity

The _Next_ and _Prev_ buttons lead to the next more recent and the previous less recent submissions respectively.

The _Gallery_, _All_, and _Scraps_ buttons open a search page with the user's gallery submissions, scraps and gallery
submissions together, and scraps submissions respectively.

### Journal

The journal page shows the journal metadata and content.

The metadata table contains clickable links to the user's page (see [User](#user) for details) and to user pages of
mentioned users.

Under the metadata table are a number of buttons that allow to download the journal, open its Fur Affinity counterpart,
and navigate the other journals from the same user.

![journal controls](https://gitlab.com/MatteoCampinoti94/falocalrepo-server/-/raw/master/doc/journal.png)

The _Download Journal as ZIP_ button generates a ZIP file containing the journal content HTML and metadata in JSON
format.

The _Open on Fur Affinity_ button opens the journal on Fur Affinity

The _Next_ and _Prev_ buttons lead to the next more recent, and the previous less recent journals respectively.

The _All_ button opens a search page with all the user's journals.