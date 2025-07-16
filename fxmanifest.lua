fx_version 'cerulean'
game 'gta5'
lua54 'yes'

name 'advance-manager'
author 'Advanced Scripts'
description 'Advanced Business Management System for FiveM'
version '1.0.0'

shared_scripts {
    '@ox_lib/init.lua',
    'shared/*.lua'
}

server_scripts {
    '@oxmysql/lib/MySQL.lua',
    'server/init.lua'
}

client_scripts {
    'client/init.lua'
}

dependencies {
    'ox_lib',
    'oxmysql',
    'qb-core'
}

provide 'advance-manager'
