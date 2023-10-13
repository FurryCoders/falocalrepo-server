<div align="center">

<img alt="logo" width="400" src="https://raw.githubusercontent.com/FurryCoders/Logos/main/logos/falocalrepo-server-transparent.png">

# FALocalRepo-Server

Web interface for [falocalrepo](https://pypi.org/project/falocalrepo/).

[![](https://img.shields.io/github/v/tag/FurryCoders/falocalrepo-server?label=github&sort=date&logo=github&color=blue)](https://github.com/FurryCoders/falocalrepo-server)
[![](https://img.shields.io/pypi/v/falocalrepo-server?logo=pypi)](https://pypi.org/project/falocalrepo-server/)
[![](https://img.shields.io/pypi/pyversions/falocalrepo-server?logo=Python)](https://www.python.org)
[![](https://img.shields.io/badge/Bootstrap-5.2.0-7952B3?logo=bootstrap&logoColor=white)](https://getbootstrap.com)

</div>

## Installation & Requirements

To install the program it is sufficient to use Python pip and get the package `falocalrepo-server`.

```shell
pip install falocalrepo-server
```

Python 3.10 or above is needed to run this program, all other dependencies are handled by pip during installation. For
information on how to install Python on your computer, refer to the official
website [Python.org](https://www.python.org/).

For the program to run, a properly formatted database created by falocalrepo needs to be present in the same folder.

The styling is based on the [Boostrap CSS framework](https://getbootstrap.com).

## Usage

```
falocalrepo-server <database> [--host HOST] [--port PORT] [--ssl-cert SSL_CERT] [--ssl-key SSL_KEY] 
                   [--redirect-http REDIRECT_PORT] [--auth <username>:<password>] [--precache] [--no-browser]
```

The server needs one argument pointing at the location of a valid [falocalrepo](https://pypi.org/project/falocalrepo/)
database and accepts optional arguments to manually set host, port, and an SSL certificate with key. By default, the
server is run on 0.0.0.0:80 for HTTP (without certificate) and 0.0.0.0:443 for HTTPS (with certificate).

The `--precache` options can be used to prepare an initial cache of results from the database to speed up searches.

When the app has finished loading, it automatically opens a browser window. To avoid this, use the `--no-browser`
option.

### Redirect Mode

The optional `--redirect-http` argument changes the app mode to redirection. In this mode the app runs a tiny server
that redirects all HTTP requests it receives on `http://HOST:PORT` to `https://HOST:REDIRECT_PORT`.

_Note:_ In redirect mode the `database` argument is not checked, so a simple `.` is sufficient.<br/>
_Note:_ In redirect mode the app does not operate the database portion of the server. To run in redirect and server
mode, two separate instances of the program are needed.

Once the server is running the web app can be accessed at the address shown in the terminal.

### Authentication

The `--auth` option allows setting up a username and password to access the server using the HTTP Basic authentication
protocol.

### Arguments

| Argument          | Default                                          |
|-------------------|--------------------------------------------------|
| `database`        | None, mandatory argument                         |
| `--host`          | 0.0.0.0                                          |
| `--port`          | 80 if no SSL certificate is given, 443 otherwise |
| `--ssl-cert`      | None                                             |
| `--ssl-key`       | None                                             |
| `--redirect-http` | None                                             |
| `--auth`          | None                                             |
| `--precache`      | False                                            |
| `--no-browser`    | True                                             |

### Examples

```shell
# Launch an HTTP server reachable from other machines using the server's hostname/IP
falocalrepo-server ~/FA.db
```

```shell
# Launch a localhost-only server on port 8080
falocalrepo-server ~/FA.db --host 127.0.0.1 --port 8080
```

```shell
# Launch a redirect server that listens to port 80 and redirects to port 443 on host 0.0.0.0
falocalrepo-server . --host 0.0.0.0 --port 80 --redirect-htpp 443
```

```shell
# Launch a server with basic authentication using 'mickey' as username and 'mouse' as password
falocalrepo-server ~/FA.db --auth mickey:mouse
```

```shell
# Launch an HTTPS server reachable from other machines using the server's hostname/IP
falocalrepo-server ~/FA.db --ssl-cert ~/FA.certificates/certificate.crt --ssl-key ~/FA.certificates/private.key 
```

```shell
# Launch a localhost-only HTTPS server on port 8443
falocalrepo-server ~/FA.db --host 127.0.0.1 --port 8443 --ssl-cert ~/FA.certificates/certificate.crt --ssl-key ~/FA.certificates/private.key 
```

## Routes

_Note:_ All the following paths are meant as paths from `<host>:<port>`.

| Route                                          | Destination                                                                             |
|------------------------------------------------|-----------------------------------------------------------------------------------------|
| `/`                                            | Show home page with general information regarding the database                          |
| `/search/`                                     | Redirects to `/search/submissions/`                                                     |
| `/search/submissions/`                         | Search & browse submissions                                                             |
| `/search/journals/`                            | Search & browse journals                                                                |
| `/search/users/`                               | Search & browse users                                                                   |
| `/settings/`                                   | Change default search settings                                                          |
| `/user/<username>/`                            | Show information regarding a specific user                                              |
| `/user/<username>/icon/`                       | Redirect to username's icon on Fur Affinity                                             |
| `/user/<username>/thumbnail/`                  | Redirect to username's icon on Fur Affinity                                             |
| `/gallery/<username>/`                         | Browse & search a user's gallery submissions                                            |
| `/scraps/<username>/`                          | Browse & search a user's scraps submissions                                             |
| `/submissions/<username>/`                     | Browse & search a user's gallery & scraps submissions                                   | 
| `/favorites/<username>/`                       | Browse & search a user's favorite submissions                                           |
| `/mentions/<username>/`                        | Browse & search the submissions where the user is mentioned                             |
| `/journals/<username>/`                        | Browse & search a user's journals                                                       |
| `/full/<submission id>/`                       | Redirect to `/submission/<submission id>/`                                              |
| `/view/<submission id>/`                       | Redirect to `/submission/<submission id>/`                                              |
| `/submission/<submission id>/`                 | View a submission                                                                       |
| `/submission/<submission id>/file/`            | Open the first submission file                                                          |
| `/submission/<submission id>/file/<n>/`        | Open the nth first submission file                                                      |
| `/submission/<submission id>/files/`           | Download all the submission files as a zip                                              |
| `/submission/<submission id>/files/<n1>-<n2>/` | Download submissions files from index n1 to index n2 (0 indexed inclusive)              |
| `/submission/<submission id>/thumbnail/`       | Open a submission thumbnail (generated for image submissions if no thumbnail is stored) |
| `/submission/<submission id>/zip/`             | Download a submission's file, description, and metadata as a ZIP archive                |
| `/journal/<journal id>/`                       | View a journal                                                                          |
| `/journal/<journal id>/zip/`                   | Download a journal's content and metadata as a ZIP archive                              |

### JSON API Routes

The following routes return information as JSON responses. They can be reached with `GET` and `POST` requests, the
former supports sending body fields as URL parameters.

| Route                              | Destination                                                                                                                                                     | Body                                                                                 |
|------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| `/json/search/<table>/`            | Perform a search on the database. The query field in the body uses the same [syntax](#query-language) as the query field in the [search page](#browse--search). | `{query?: str, offset?: int, limit?: int, sort?: str, order?: Union["asc", "desc"]}` |
| `/json/user/<username>`            | Get user metadata and total submissions/journals                                                                                                                | None                                                                                 |
| `/json/submission/<submission id>` | Get submission metadata and comments                                                                                                                            | None                                                                                 |
| `/json/journal/<journal id>`       | Get journal metadata and comments                                                                                                                               | None                                                                                 |

## Pages

_Note:_ the images used in the following sections were taken using light mode, but all pages also support dark mode.

### Home

The home page displays general information about the database and contains links to browse and search pages for the
various tables.

The information table displays the total number of submissions, journals, and users together with the version of the
database. Clicking on any of the counters open the relevant search & browse page.

### Browse & Search

The browse and search pages allow to explore the submissions/journals contained in the database. Searches are performed
case-insensitively using a simple syntax in the form `@field term [[| &] term ...]` which allows logic operators,
parentheses and start/end of field matching, see [Query Language](#query-language) for details.

Search terms for submissions and journals default to the `any` field if none is used, while the `username` field is used
for users searches.

The controls at the top of the page allow to query the database and control the visualisation of the results.

<div align="center">
<img alt="" src="https://raw.githubusercontent.com/FurryCoders/falocalrepo-server/master/doc/search-form.png" width="600">
</div>

The _Search_ input allows to insert the search query.

The _Field_ menu allows to insert a specific search field using a simple dropdown menu.

The _Sort_ and adjacent order menus change the sorting field and order of the search results. Submissions and journals
default to descending ID, while users default to ascending username.

The _View_ menu allows changing between the (default) grid view to a list (table) view

The _Search_ button submits the search request using the current query and sorting settings.

The _Browse_ button resets the current search query and reverts to browse mode (all entries).

The _FA_ button opens the current search on Fur Affinity, translating the shared search and sorting fields (tags,
author, description, and fileurl/fileext). The button is only available when searching submissions.

The gear button opens the search settings, the question mark button shows a quick help about the query language.

Under the search controls are the number of results and current page.

<div align="center">
<img alt="" src="https://raw.githubusercontent.com/FurryCoders/falocalrepo-server/master/doc/search-nav.png" width="400">
</div>

Under the results numbers are the page controls. _First_ leads to page 1, _Prev_ leads to the previous page, _Next_
leads to the next page, and _Last_ leads to the last page. These controls are also available at the bottom of the page.

In grid view, the results are presented using cards containing the same information as the list view, with the addition
of thumbnails for submissions. When searching for submissions or journals, clicking on the card footer (containing the
date and author) will open the author's page. Submissions with more than one file will display a small counter with the
number of files in the upper right corner of the card.

<div align="center">
<img src="https://raw.githubusercontent.com/FurryCoders/falocalrepo-server/master/doc/search-card.png" width="200">
</div>

In list view, the results are presented in a table with the most important columns: ID, AUTHOR, DATE, and TITLE (
submissions and journals); USERNAME, FOLDERS, and ACTIVE (users). On small screens some of these columns are shortened
or removed.

<div align="center">
<img src="https://raw.githubusercontent.com/FurryCoders/falocalrepo-server/master/doc/search-list.png" width="800">
</div>

#### Compatibility with Fur Affinity Search

Most Fur Affinity search queries (and links) are fully compatible with the program.

Except for the _NOT_ (!) operator, which follows different syntax rules, all Fur Affinity search fields are fully
supported: `@lower` (treated as `@author`), `@keywords` (treated as `@tags`), `@message` (treated as `@description`)
, `@title` (treated as `@title`), `@filename` (treated as `@fileurl`).

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

The search uses the `@any` field by default for submissions and journals, allowing to do general searches without
specifying a field. The `@any` field does not include the `FAVORITE`, `FILESAVED`, `USERUPDATE`, and `ACTIVE` fields and
must be searched manually using the respective query fields. When searching users, `@username` is the default field.

Search terms that are not separated by a logic operator are considered _AND_ terms (i.e. `a b c` -> `a & b & c`).

Except for the `ID`, `FILESAVED`, `USERUPDATE`, and `ACTIVE` fields, all search terms are searched through the
whole content of the various fields: i.e. `@description cat` will match any item whose description field contains "cat".
To match items that contain only "cat" (or start with, end with, etc.), the `%`, `_`, `^`, and `$` operators need to be
used (e.g. `@description ^cat`).

Search terms for `ID`, `FILESAVED`, `USERUPDATE`, and `ACTIVE` are matched exactly as they are: i.e. `@id 1` will match
only items whose ID field is exactly equal to "1", to match items that contain "1" the `%`, `_`, `^`, or `$` operators
need to be used (e.g. `@id %1%`).

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

### Search Settings

The search settings page allows modifying the sorting, ordering, and viewing option that are applied by default to the
various searches. Settings can be saved to the database if it is writable, otherwise they are simply saved for the
current session and reset when the program stops.

Settings values are saved in the `SETTINGS` table with the `SERVER.SEARCH` setting name.

### User

The user page shows information about submissions and journals related to a user (gallery, scraps, favorites, mentions,
and journals) and what folders have been set for download. See [falocalrepo](https://pypi.org/project/falocalrepo/) for
more details on this. The user's profile will be displayed if present in the database.

Clicking on any of the counters opens the relevant results via the search interface, allowing to refine the search
further.

The _Next_ and _Prev_ buttons move to the respective users in ascending alphabetical order.

### Submission

The submission page shows the submission file(s) (if present), the submission metadata, and the description.

Image, audio, video, and plain text submission files are displayed directly in the page, others (e.g. PDF files) will
display a link to open them. Clicking on image files will enlarge them to fill the width of the screen for easier
viewing. Video files can be enlarged by using the zoom button under them.

When a submission has two or more files, a toolbar appears below the file section with buttons to switch between the
different files, show the files in a grid view, and enlarge non-image files (text, video, etc.).

<div align="center">
<img alt="" src="https://raw.githubusercontent.com/FurryCoders/falocalrepo-server/master/doc/buttons-file-switcher.png" width="200">
</div>

The metadata table contains clickable links to the user's page (see [User](#user) for details), tags, category, species,
gender, rating, folder (gallery/scraps), and to user pages of favouring and mentioned users.

The description is displayed as-is except for user icons, which are replaced by `@username` styled links to avoid
display errors caused by expired icon links.

Under the metadata table are a number of buttons that allow to access the submission file, open its Fur Affinity
counterpart, and navigate the other submissions from the author.

<div align="center">
<img alt="" src="https://raw.githubusercontent.com/FurryCoders/falocalrepo-server/master/doc/buttons-submission.png" width="400">
</div>

The download _File_ button downloads the submission file (if present). If more than one file is present, then the button
downloads a zip file containing all submission files.

The download _ZIP_ button generates a ZIP file containing the submission file, submission thumbnail, description HTML,
and metadata and comments in JSON format.

The _FA_ button opens the submission on Fur Affinity

The _Next_ and _Prev_ buttons lead to the next more recent and the previous less recent submissions respectively.

The _Gallery_, _All_, and _Scraps_ buttons open a search page with the user's gallery submissions, scraps and gallery
submissions together, and scraps submissions respectively.

To view the currently selected submission file when scrolling down the page, the button in the lower right corner can be
used to open the image in a floating overlay that will remain at the top of the page view.

<img alt="" src="https://raw.githubusercontent.com/FurryCoders/falocalrepo-server/master/doc/buttons-submission-overlay.png" width="50">

The comments to the submission can be found below the description, and can be reached quickly by clicking on the
floating comments button that appears in the lower right corner of the screen if the submission has comments.

<img alt="" src="https://raw.githubusercontent.com/FurryCoders/falocalrepo-server/master/doc/buttons-comments-link.png" width="50">

Each comment contains the author (with a link to their user page), post date, and links to the comment itself and, if
the comment is a reply, its parent comments.

<div align="center">
<img alt="" src="https://raw.githubusercontent.com/FurryCoders/falocalrepo-server/master/doc/comment-card.png" width="400">
</div>

The button furthest to the left (arrow pointing up and to the left) links to the first comment in a reply chain. The
middle button (bent arrow pointing to the left) links to the previous comment in the reply chain. The link button
furthest to the right is a link to that specific comment.

### Journal

The journal page shows the journal metadata and content.

The metadata table contains clickable links to the user's page (see [User](#user) for details) and to user pages of
mentioned users.

Under the metadata table are a number of buttons that allow to download the journal, open its Fur Affinity counterpart,
and navigate the other journals from the same user.

<div align="center">
<img alt="" src="https://raw.githubusercontent.com/FurryCoders/falocalrepo-server/master/doc/buttons-journal.png" width="400">
</div>

The download _ZIP_ button generates a ZIP file containing the journal content HTML and metadata and comments in JSON
format.

The _FA_ button opens the journal on Fur Affinity

The _Next_ and _Prev_ buttons lead to the next more recent, and the previous less recent journals respectively.

The _All_ button opens a search page with all the user's journals.

The comments to the journal can be found below the journal text, and can be reached quickly by clicking on the floating
comments button that appears in the lower right corner of the screen if the journal has comments.

<img alt="" src="https://raw.githubusercontent.com/FurryCoders/falocalrepo-server/master/doc/buttons-comments-link.png" width="50">

Each comment contains the author (with a link to their user page), post date, and links to the comment itself and, if
the comment is a reply, its parent comments.

<div align="center">
<img alt="" src="https://raw.githubusercontent.com/FurryCoders/falocalrepo-server/master/doc/comment-card.png" width="400">
</div>

The button furthest to the left (arrow pointing up and to the left) links to the first comment in a reply chain. The
middle button (bent arrow pointing to the left) links to the previous comment in the reply chain. The link button
furthest to the right is a link to that specific comment.

### BBCode

When the database is in BBCode mode a new buttons appears along submission descriptions, journal contents, and user
profiles to switch between the rendered HTML and the BBCode stored in the database.

<div align="center">
<img alt="" src="https://raw.githubusercontent.com/FurryCoders/falocalrepo-server/master/doc/buttons-bbcode.png" width="120">
</div>

_Note:_ the BBCode to HTML conversion is still a work in progress and some content may be rendered incorrectly; please
open
an [issue](https://github.com/FurryCoders/falocalrepo-server/issues) if you encounter any error :)
