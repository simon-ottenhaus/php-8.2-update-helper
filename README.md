# A simple python script that helps with migration from php 8.1 to php 8.2

In php 8.2 dynamic class properties are deprecated. Example:
    
```php
class Example {
    public function __construct() {
        $this->property = 'value'; // Deprecated
    }        
}
```

## Usage

1. Clone this repository or download the `php-8.2-update-helper.py` and `requirements.txt` files.
2. Create a virtual environment.
3. Activate the virtual environment.
4. Install the requirements.
5. Run the script.

```bash
git clone ...
cd php-8.2-update-helper
python3 -m venv venv
source venv/bin/activate   # Linux
# & venv/Scripts/Acivate.ps1 # Windows
pip install -r requirements.txt
python php-8.2-update-helper.py
```

It will write a file `php-8.2-update-helper.log` with the results.

## How it works

The script uses simple regexes to detect:

- php classes
- declared properties
- used properties

Then it compares the declared properties with the used properties and writes the results to the log file.
The log file also contains proposed fixes.