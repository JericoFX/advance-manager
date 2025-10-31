fx_version 'cerulean'
game 'gta5'
lua54 'yes'

name 'advance-manager'
author 'JericoFX'
description 'Advanced Business Management System for FiveM'
version '0.0.2'

shared_scripts {
    '@ox_lib/init.lua',
    'shared/*.lua'
}

server_scripts {
    '@oxmysql/lib/MySQL.lua',
    'server/init.lua'
}

client_scripts {
    'client/init.lua',
    'client/ui-handler.lua'
}

dependencies {
    'ox_lib',
    'oxmysql',
    'qb-core'
}

ui_page 'ui/index.html'

files {
    'ui/index.html',
    'ui/css/*.css',
    'ui/js/*.js'
}

provide 'advance-manager'
