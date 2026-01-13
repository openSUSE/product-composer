from ..utils.loggerutils import die

def get_cpeid(yml):
    if yml['product_type'] not in ('base', 'module', 'extension', None):
        die('Undefined product-type')
    cpeid = f"cpe:/o:{yml['vendor']}:{yml['name']}:{yml['version']}"
    if yml['update']:
        cpeid = cpeid + f":{yml['update']}"
        if yml['edition']:
            cpeid = cpeid + f":{yml['edition']}"
    elif yml['edition']:
        cpeid = cpeid + f"::{yml['edition']}"

    return cpeid.lower()
