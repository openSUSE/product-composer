
def get_cpeid(yml):
    match yml['product_type']:
        case 'base' | None:
            product_type = '/o'
        case 'module' | 'extension':
            product_type = '/a'
        case _:
            die('Undefined product-type')
    cpeid = f"cpe:{product_type}:{yml['vendor']}:{yml['name']}:{yml['version']}"
    if yml['update']:
        cpeid = cpeid + f":{yml['update']}"
        if yml['edition']:
            cpeid = cpeid + f":{yml['edition']}"
    elif yml['edition']:
        cpeid = cpeid + f"::{yml['edition']}"

    return cpeid
