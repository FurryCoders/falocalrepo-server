# FALocalRepo-Server

Web interface for [falocalrepo](https://pypi.org/project/falocalrepo/).

## Installation & Requirements

To install the program it is sufficient to use Python pip and get the package `falocalrepo-server`.

```shell
python3 -m pip install falocalrepo-server
```

Python 3.8 or above is needed to run this program, all other dependencies are handled by pip during installation. For information on how to install Python on your computer, refer to the official website [Python.org](https://www.python.org/).

For the program to run, a properly formatted database created by falocalrepo needs to be present in the same folder.

## Usage

```
falocalrepo-server [<host>:<port>]
```

The command accepts a single optional argument to manually set host and port. By default the server is run on 0.0.0.0:8080.

Once the server is running - it will display status messages in the terminal - the web app can be accessed at http://0.0.0.0:8080/, or any manually set host/port combination.

_Note:_ All the following paths are meant as paths from `<host>:<port>`.

The root folder `/` displays basic information on the database and has links to perform submissions and journal searches.

### User

The `/user/<username>` path displays basic statistics of a user stored in the database. Clicking on gallery/scraps or journals counters opens submissions and journals by the user respectively.

The `/submissions/<username>` and `/journals/<username>` paths open submissions and journals by the user respectively.

### Search

The server search interface allows to search both submissions and journals. Respectively, these can be reached at `/search/submissions` and `/search/journals`. The `/search/` path defaults to submissions search.

The interface supports the search fields supported by the command line database search commands. To add a field press on the `+` button after selecting one in the dropdown menu. The `-` buttons allow to remove a field from the search.

Fields can be added multiple times and will act as OR options.

The order field allows to sort the search result. By default submissions and journals are sorted by author and ID. For a list of possible sorting fields, see [#Submissions](https://gitlab.com/MatteoCampinoti94/FALocalRepo#submissions) and [#Journals](https://gitlab.com/MatteoCampinoti94/FALocalRepo#journals) in the database section of FALocalRepo readme.

Fields are matched using the SQLite [`like`](https://sqlite.org/lang_expr.html#like) expression which allows for limited pattern matching. See [`database` command](https://gitlab.com/MatteoCampinoti94/FALocalRepo#database) for more details.

The `/submissions/<username>/` and `/journals/<username>/` paths allow to quickly open a search for submissions and journals by `<username>`. `/search/submissions/<username>/` and `/search/journals/<username>/` are also allowed.

Results of the search are displayed 50 per page in a table. Clicking on any row opens the specific item. Clicking on the table headers allows to perform re-sort the search results.

### Submissions & Journals

Submissions and journals can be accessed respectively at `/submission/<id>` and `/journal/<id>`. All the metadata, content and files that are recorded in the database are displayed in these pages.

Submission files can be accessed at `/submission/<id>/file`.
