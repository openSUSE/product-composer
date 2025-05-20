import os

def create_media_dir(maindir, vendorstr, identstr, products):
    media1dir = maindir + '/' + 'media.1'
    if not os.path.isdir(media1dir):
        os.mkdir(media1dir)  # we do only support seperate media atm
    with open(media1dir + '/media', 'w') as media_file:
        media_file.write(vendorstr + "\n")
        media_file.write(identstr + "\n")
        media_file.write("1\n")
    if products:
        with open(media1dir + '/products', 'w') as products_file:
            for productname in products:
                products_file.write('/ ' + productname + "\n")