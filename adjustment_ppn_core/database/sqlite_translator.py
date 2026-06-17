import re
import datetime

def sqlite_date_format(date_str, format_str):
    """
    Mock implementation of MySQL's DATE_FORMAT function for SQLite.
    Translates MySQL format specifiers to Python strftime format specifiers
    and formats the date string accordingly.
    """
    if not date_str or str(date_str).strip() in ('', '0000-00-00', '0000-00-00 00:00:00'):
        return ""
        
    if isinstance(date_str, (datetime.datetime, datetime.date)):
        dt = date_str
    else:
        date_str = str(date_str).strip()
            
        dt = None
        # Common date formats in our databases
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%i:%s', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d'):
            py_fmt = fmt.replace('%i', '%M').replace('%s', '%S')
            try:
                dt = datetime.datetime.strptime(date_str, py_fmt)
                break
            except ValueError:
                continue
                
        if dt is None:
            # Fallback simple parser for ISO-like dates
            try:
                parts = date_str.replace('T', ' ').split(' ')
                d_parts = list(map(int, parts[0].split('-')))
                t_parts = [0, 0, 0]
                if len(parts) > 1:
                    t_parts = list(map(int, parts[1].split(':')))
                while len(t_parts) < 3:
                    t_parts.append(0)
                dt = datetime.datetime(d_parts[0], d_parts[1], d_parts[2], t_parts[0], t_parts[1], t_parts[2])
            except Exception:
                return date_str  # Return original if we cannot parse
                
    # Translate MySQL format codes to Python strftime format codes in the correct order:
    # - %M -> %B (Month name)
    # - %h -> %I (12-hour hour)
    # - %W -> %A (Weekday name)
    # - %T -> %H:%M:%S (24-hour time)
    # - %r -> %I:%M:%S %p (12-hour time)
    # - %i -> %M (Minutes)
    # - %s or %S -> %S (Seconds)
    py_format = format_str
    py_format = py_format.replace('%M', '%B')
    py_format = py_format.replace('%h', '%I')
    py_format = py_format.replace('%W', '%A')
    py_format = py_format.replace('%T', '%H:%M:%S')
    py_format = py_format.replace('%r', '%I:%M:%S %p')
    py_format = py_format.replace('%i', '%M')
    py_format = py_format.replace('%s', '%S')
    py_format = py_format.replace('%S', '%S')
    
    try:
        return dt.strftime(py_format)
    except Exception:
        return date_str


def is_pk_constraint_for_col(line, col_name):
    """
    Checks if a DDL line is a PRIMARY KEY constraint for a specific column.
    E.g., PRIMARY KEY (`URUTAN`)
    """
    line_clean = line.strip().upper()
    if not line_clean.startswith('PRIMARY KEY'):
        return False
    m = re.search(r'\((.*)\)', line_clean)
    if m:
        cols = [c.strip(' `"') for c in m.group(1).split(',')]
        if len(cols) == 1 and cols[0] == col_name.upper():
            return True
    return False


def strip_comments_and_whitespace(sql_stmt):
    """
    Strips single-line (-- or #) and multi-line (/*...*/) SQL comments
    from the SQL statement, and cleans trailing/leading whitespace.
    Preserves comments inside single or double quotes.
    """
    if not sql_stmt:
        return ""
    
    clean_chars = []
    inside_single_quote = False
    inside_double_quote = False
    escaped = False
    
    i = 0
    n = len(sql_stmt)
    while i < n:
        char = sql_stmt[i]
        
        if escaped:
            clean_chars.append(char)
            escaped = False
            i += 1
            continue
            
        if char == '\\':
            clean_chars.append(char)
            escaped = True
            i += 1
            continue
            
        if char == "'" and not inside_double_quote:
            inside_single_quote = not inside_single_quote
            clean_chars.append(char)
            i += 1
            continue
            
        if char == '"' and not inside_single_quote:
            inside_double_quote = not inside_double_quote
            clean_chars.append(char)
            i += 1
            continue
            
        if not inside_single_quote and not inside_double_quote:
            # Check for multi-line comment: /* ... */
            if char == '/' and i + 1 < n and sql_stmt[i+1] == '*':
                i += 2
                while i < n:
                    if sql_stmt[i] == '*' and i + 1 < n and sql_stmt[i+1] == '/':
                        i += 2
                        break
                    i += 1
                continue
                
            # Check for single-line comment: -- or #
            if char == '#' or (char == '-' and i + 1 < n and sql_stmt[i+1] == '-'):
                while i < n and sql_stmt[i] != '\n':
                    i += 1
                continue
                
        clean_chars.append(char)
        i += 1
        
    return "".join(clean_chars).strip()


def parse_create_table_to_sqlite(sql_stmt):
    """
    Parses MySQL DDL CREATE TABLE syntax to SQLite compatible syntax.
    Removes engines, character sets, incompatible key definitions, and
    translates auto_increment to SQLite format.
    """
    # Extract the header (up to the first '('), body, and footer
    first_paren = sql_stmt.find('(')
    last_paren = sql_stmt.rfind(')')
    if first_paren == -1 or last_paren == -1 or last_paren <= first_paren:
        return sql_stmt
        
    header = sql_stmt[:first_paren + 1]
    body = sql_stmt[first_paren + 1:last_paren]
    
    # Process body lines
    raw_lines = body.split('\n')
    filtered_lines = []
    
    # First pass: find any auto_increment column
    autoincrement_col = None
    for line in raw_lines:
        if 'auto_increment' in line.lower():
            m = re.search(r'^\s*`?([a-zA-Z0-9_]+)`?', line)
            if m:
                autoincrement_col = m.group(1)
                break
                
    for line in raw_lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        # Ignore comments
        if line_str.startswith('--') or line_str.startswith('#') or (line_str.startswith('/*') and line_str.endswith('*/')):
            continue
            
        # Translate UNIQUE KEY / UNIQUE INDEX to UNIQUE first
        line_str = re.sub(r'(?i)\bUNIQUE\s+(?:KEY|INDEX)\s+`?\w+`?\s*\(', 'UNIQUE (', line_str)
        
        line_clean = line_str.rstrip().rstrip(',')
        
        # Detect key/index constraints using a safe regex check and ensure it ends with ) column list
        is_key_constraint = False
        if re.match(r'^\s*(?:UNIQUE\s+|FULLTEXT\s+|SPATIAL\s+)?(?:KEY|INDEX)\b', line_clean, re.IGNORECASE):
            if line_clean.endswith(')'):
                datatypes = r'\b(?:INT|INTEGER|VARCHAR|CHAR|DOUBLE|DECIMAL|FLOAT|TEXT|DATETIME|TIMESTAMP|BLOB|TINYINT|SMALLINT|BIGINT|ENUM|BOOLEAN|DATE|TIME)\b'
                if not re.search(datatypes, line_clean, re.IGNORECASE):
                    is_key_constraint = True
                    
        if is_key_constraint:
            continue
            
        # If autoincrement_col is present, drop all table-level PRIMARY KEY constraints
        if autoincrement_col and re.match(r'^\s*PRIMARY\s+KEY\b', line_clean, re.IGNORECASE):
            continue
            
        # Strip character set and collate properties
        line_str = re.sub(r'(?i)\bCHARACTER\s+SET\s+\w+', '', line_str)
        line_str = re.sub(r'(?i)\bCOLLATE\s+\w+', '', line_str)
        line_str = re.sub(r'\s+', ' ', line_str) # clean extra spaces
        
        # Rewrite the autoincrement column definition for SQLite
        if autoincrement_col:
            m = re.match(r'^\s*`?' + re.escape(autoincrement_col) + r'`?\b', line_str, re.IGNORECASE)
            if m:
                line_str = f"`{autoincrement_col}` INTEGER PRIMARY KEY AUTOINCREMENT"
                
        # Clean trailing commas from each line in filtered_lines before joining
        line_str_clean = line_str.rstrip().rstrip(',')
        if line_str_clean:
            filtered_lines.append(line_str_clean)
        
    new_body = '\n  ' + ',\n  '.join(filtered_lines) + '\n'
    new_ddl = header + new_body + ');'
    return new_ddl


def make_sqlite_compatible(sql_stmt):
    """
    Processes a SQL statement and converts it to SQLite compatible format.
    Handles CREATE TABLE transformation and string literal escape cleaning.
    """
    cleaned = strip_comments_and_whitespace(sql_stmt)
    if not cleaned:
        return None
        
    stmt_upper = cleaned.upper()
    if (stmt_upper.startswith('SET ') or 
        stmt_upper.startswith('LOCK TABLES') or 
        stmt_upper.startswith('UNLOCK TABLES') or
        stmt_upper.startswith('START TRANSACTION') or
        stmt_upper.startswith('COMMIT') or
        stmt_upper.startswith('ROLLBACK') or
        not stmt_upper):
        return None
        
    if 'CREATE TABLE' in stmt_upper:
        return parse_create_table_to_sqlite(cleaned)
    else:
        # For INSERT and other queries, replace MySQL string escapes with SQLite equivalents
        # MySQL \' -> SQLite ''
        # MySQL \" -> SQLite "
        # MySQL \\ -> SQLite \
        cleaned = cleaned.replace("\\'", "''")
        cleaned = cleaned.replace('\\"', '"')
        cleaned = cleaned.replace('\\\\', '\\')
        return cleaned


def translate_query(query_str):
    """
    Replaces %s placeholders with ? in SQLite mode, preserving them inside quotes.
    Uses a character-by-character state machine to correctly handle escaped
    characters (like \') and double/single quotes.
    """
    inside_single = False
    inside_double = False
    escaped = False
    result = []
    
    i = 0
    n = len(query_str)
    while i < n:
        char = query_str[i]
        
        # Check for escaped characters
        if escaped:
            result.append(char)
            escaped = False
            i += 1
            continue
            
        if char == '\\':
            result.append(char)
            escaped = True
            i += 1
            continue
            
        if char == "'" and not inside_double:
            inside_single = not inside_single
            result.append(char)
            i += 1
            continue
            
        if char == '"' and not inside_single:
            inside_double = not inside_double
            result.append(char)
            i += 1
            continue
            
        # Check if we see '%s'
        if char == '%' and i + 1 < n and query_str[i + 1] == 's':
            if not inside_single and not inside_double:
                # Ensure it is a stand-alone placeholder
                if i + 2 >= n or (not query_str[i + 2].isalnum() and query_str[i + 2] != '_'):
                    result.append('?')
                    i += 2
                    continue
        
        result.append(char)
        i += 1
        
    return "".join(result)