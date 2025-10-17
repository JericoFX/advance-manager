local QBCore = exports['qb-core']:GetCoreObject()

-- Estado de la UI
local isUIOpen = false

-- Función para obtener el jugador más cercano
local function getNearestPlayer()
    local playerPed = PlayerPedId()
    local playerCoords = GetEntityCoords(playerPed)
    local players = GetActivePlayers()
    local closestPlayer = nil
    local closestDistance = math.huge
    
    for _, player in pairs(players) do
        if player ~= PlayerId() then
            local targetPed = GetPlayerPed(player)
            local targetCoords = GetEntityCoords(targetPed)
            local distance = #(playerCoords - targetCoords)
            
            if distance < closestDistance and distance < 5.0 then
                closestDistance = distance
                closestPlayer = GetPlayerServerId(player)
            end
        end
    end
    
    return closestPlayer
end

-- Configurar NUI callbacks
RegisterNUICallback('advance-manager:getPlayerBusiness', function(data, cb)
    lib.callback('advance-manager:getPlayerBusiness', false, function(result)
        cb(result)
    end)
end)

RegisterNUICallback('advance-manager:depositFunds', function(data, cb)
    lib.callback('advance-manager:getPlayerBusiness', false, function(business)
        if business then
            lib.callback('advance-manager:depositFunds', false, function(success, message)
                cb(success, message)
            end, business.id, data.amount)
        else
            cb(false, 'No business found')
        end
    end)
end)

RegisterNUICallback('advance-manager:withdrawFunds', function(data, cb)
    lib.callback('advance-manager:getPlayerBusiness', false, function(business)
        if business then
            lib.callback('advance-manager:withdrawFunds', false, function(success, message)
                cb(success, message)
            end, business.id, data.amount)
        else
            cb(false, 'No business found')
        end
    end)
end)

RegisterNUICallback('advance-manager:hireEmployee', function(data, cb)
    lib.callback('advance-manager:getPlayerBusiness', false, function(business)
        if business then
            local wage = tonumber(data.wage)
            local playerId = tonumber(data.playerId)
            local grade = tonumber(data.grade)

            if not wage or wage <= 0 then
                cb(false, 'Invalid wage provided')
                return
            end

            if not playerId or playerId <= 0 then
                cb(false, 'Invalid player ID')
                return
            end

            if not grade then
                cb(false, 'Invalid grade')
                return
            end

            lib.callback('advance-manager:hireEmployee', false, function(success, message)
                cb(success, message)
            end, business.id, playerId, grade, wage)
        else
            cb(false, 'No business found')
        end
    end)
end)

RegisterNUICallback('advance-manager:fireEmployee', function(data, cb)
    lib.callback('advance-manager:getPlayerBusiness', false, function(business)
        if business then
            local citizenId = data.citizenid

            if type(citizenId) ~= 'string' or citizenId == '' then
                cb(false, 'Invalid citizen ID')
                return
            end

            lib.callback('advance-manager:fireEmployee', false, function(success, message)
                cb(success, message)
            end, business.id, citizenId)
        else
            cb(false, 'No business found')
        end
    end)
end)

RegisterNUICallback('advance-manager:getBusinessEmployees', function(data, cb)
    lib.callback('advance-manager:getPlayerBusiness', false, function(business)
        if business then
            lib.callback('advance-manager:getBusinessEmployees', false, function(employees)
                cb(employees)
            end, business.id)
        else
            cb(false)
        end
    end)
end)

RegisterNUICallback('advance-manager:updateEmployeeWage', function(data, cb)
    lib.callback('advance-manager:getPlayerBusiness', false, function(business)
        if business then
            local citizenId = data.citizenid
            local newWage = tonumber(data.newWage)

            if type(citizenId) ~= 'string' or citizenId == '' then
                cb(false, 'Invalid citizen ID')
                return
            end

            if not newWage or newWage <= 0 then
                cb(false, 'Invalid wage amount')
                return
            end

            lib.callback('advance-manager:updateEmployeeWage', false, function(success, message)
                cb(success, message)
            end, business.id, citizenId, newWage)
        else
            cb(false, 'No business found')
        end
    end)
end)

RegisterNUICallback('advance-manager:updateEmployeeGrade', function(data, cb)
    lib.callback('advance-manager:getPlayerBusiness', false, function(business)
        if business then
            local citizenId = data.citizenid
            local newGrade = tonumber(data.newGrade)
            local wage = data.wage and tonumber(data.wage) or nil

            if type(citizenId) ~= 'string' or citizenId == '' then
                cb(false, 'Invalid citizen ID')
                return
            end

            if not newGrade or newGrade < 0 then
                cb(false, 'Invalid grade level')
                return
            end

            if wage ~= nil and wage <= 0 then
                cb(false, 'Invalid wage amount')
                return
            end

            lib.callback('advance-manager:updateEmployeeGrade', false, function(success, message)
                cb(success, message)
            end, business.id, citizenId, newGrade)
        else
            cb(false, 'No business found')
        end
    end)
end)

RegisterNUICallback('advance-manager:getBusinessFunds', function(data, cb)
    lib.callback('advance-manager:getPlayerBusiness', false, function(business)
        if business then
            lib.callback('advance-manager:getBusinessFunds', false, function(funds)
                cb(funds)
            end, business.id)
        else
            cb(false)
        end
    end)
end)

RegisterNUICallback('advance-manager:getNearestPlayer', function(data, cb)
    local nearestPlayer = getNearestPlayer()
    cb(nearestPlayer)
end)

-- Callback para cerrar la UI
RegisterNUICallback('closeUI', function(data, cb)
    SetNuiFocus(false, false)
    isUIOpen = false
    cb('ok')
end)

-- Función para abrir la UI
local function openBusinessUI()
    if isUIOpen then return end
    
    SetNuiFocus(true, true)
    SendNUIMessage({
        action = 'openUI'
    })
    isUIOpen = true
end

-- Función para cerrar la UI
local function closeBusinessUI()
    if not isUIOpen then return end
    
    SetNuiFocus(false, false)
    SendNUIMessage({
        action = 'closeUI'
    })
    isUIOpen = false
end

-- Exportar funciones
exports('openBusinessUI', openBusinessUI)
exports('closeBusinessUI', closeBusinessUI)

-- Registro de eventos
RegisterNetEvent('advance-manager:openUI', function()
    openBusinessUI()
end)

RegisterNetEvent('advance-manager:closeUI', function()
    closeBusinessUI()
end)

-- Comando para abrir la UI
RegisterCommand('businessui', function()
    if isUIOpen then
        closeBusinessUI()
    else
        openBusinessUI()
    end
end, false)

-- Tecla para abrir/cerrar (F6 por defecto)
RegisterKeyMapping('businessui', 'Toggle Business UI', 'keyboard', 'F6')

print('[advance-manager] UI handler initialized')
