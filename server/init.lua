QBCore = exports['qb-core']:GetCoreObject()

-- Initialize server-side cache for employees (more secure than GlobalState)
local EmployeeCache = {}
local deepClone = lib.table.deepclone
local round = lib.math.round

-- Load modules
local Business = require 'server.modules.business'
local Employees = require 'server.modules.employees'

-- Function to get employee cache
local function GetEmployeeCache()
    return deepClone(EmployeeCache)
end

-- Function to set employee cache
local function SetEmployeeCache(cache)
    EmployeeCache = cache
end

-- Function to get employees for specific business from cache
local function GetEmployeesFromCache(businessId)
    local employees = EmployeeCache[tostring(businessId)]
    return employees and deepClone(employees) or {}
end

-- Function to set employees for specific business in cache
local function SetEmployeesInCache(businessId, employees)
    EmployeeCache[tostring(businessId)] = employees
end

-- Make cache functions available to employees module
Employees.GetCache = GetEmployeeCache
Employees.SetCache = SetEmployeeCache
Employees.GetFromCache = GetEmployeesFromCache
Employees.SetInCache = SetEmployeesInCache

CreateThread(function()
    MySQL.query([[
        CREATE TABLE IF NOT EXISTS `businesses` (
            `id` INT(11) NOT NULL AUTO_INCREMENT,
            `name` VARCHAR(255) NOT NULL,
            `owner` VARCHAR(50) NOT NULL,
            `job_name` VARCHAR(50) NOT NULL,
            `funds` BIGINT(20) NOT NULL DEFAULT 0,
            `metadata` LONGTEXT DEFAULT NULL,
            PRIMARY KEY (`id`),
            INDEX (`owner`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    ]])

    MySQL.query([[
        CREATE TABLE IF NOT EXISTS `business_employees` (
            `id` INT(11) NOT NULL AUTO_INCREMENT,
            `business_id` INT(11) NOT NULL,
            `citizenid` VARCHAR(50) NOT NULL,
            `grade` INT(11) NOT NULL,
            `wage` INT(11) NOT NULL DEFAULT 0,
            PRIMARY KEY (`id`),
            FOREIGN KEY (`business_id`) REFERENCES `businesses`(`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    ]])

    print('[advance-manager] Database tables initialized.')

    -- Load all employees to cache
    Employees.LoadAllToCache()

    lib.cron.new('*/15 * * * *', function()
        local success, err = pcall(Employees.LoadAllToCache)

        if not success then
            lib.print.error(('[advance-manager] Failed to refresh employee cache: %s'):format(err))
        end
    end, { maxDelay = 60 })
end)

-- Admin commands
lib.addCommand('createbusiness', {
    help = 'Create a new business',
    params = {
        {name = 'name', type = 'string', help = 'Business name'},
        {name = 'owner', type = 'playerId', help = 'Owner player ID'},
        {name = 'jobName', type = 'string', help = 'Job name'},
        {name = 'funds', type = 'number', help = 'Starting funds', optional = true}
    },
    restricted = 'group.admin'
}, function(source, args, raw)
    local targetPlayer = QBCore.Functions.GetPlayer(args.owner)
    if not targetPlayer then
        TriggerClientEvent('ox_lib:notify', source, {
            title = 'Error',
            description = 'Player not found',
            type = 'error'
        })
        return
    end
    
    local success, result = Business.Create(args.name, targetPlayer.PlayerData.citizenid, args.jobName, args.funds or 0)
    
    if success then
        TriggerClientEvent('ox_lib:notify', source, {
            title = 'Success',
            description = 'Business created successfully',
            type = 'success'
        })
        
        TriggerClientEvent('ox_lib:notify', args.owner, {
            title = 'Business Created',
            description = 'You are now the owner of ' .. args.name,
            type = 'success'
        })
    else
        TriggerClientEvent('ox_lib:notify', source, {
            title = 'Error',
            description = result,
            type = 'error'
        })
    end
end)

-- Exports
exports('createBusiness', function(name, owner, jobName, startingFunds, metadata)
    return Business.Create(name, owner, jobName, startingFunds, metadata)
end)

exports('getBusinessById', function(businessId)
    return Business.GetById(businessId)
end)

exports('getBusinessByJob', function(jobName)
    return Business.GetByJob(jobName)
end)

exports('getBusinessByOwner', function(citizenId)
    return Business.GetByOwner(citizenId)
end)

exports('updateBusinessFunds', function(businessId, amount, isWithdrawal)
    return Business.UpdateFunds(businessId, amount, isWithdrawal)
end)

exports('setBusinessFunds', function(businessId, amount)
    return Business.SetFunds(businessId, amount)
end)

exports('getBusinessFunds', function(businessId)
    return Business.GetFunds(businessId)
end)

exports('hasBusinessPermission', function(citizenId, businessId, permission)
    return Business.HasPermission(citizenId, businessId, permission)
end)

exports('isBusinessBoss', function(citizenId, businessId)
    return Business.IsBoss(citizenId, businessId)
end)

-- Employee exports
exports('getBusinessEmployees', function(businessId)
    return Employees.GetAll(businessId)
end)

exports('getBusinessEmployeesFromCache', function(businessId)
    return Employees.GetFromCache(businessId)
end)

exports('getEmployeeByBusinessAndCitizen', function(businessId, citizenId)
    return Employees.GetByBusinessAndCitizen(businessId, citizenId)
end)

exports('getAllEmployeesCache', function()
    return EmployeeCache
end)

exports('isEmployeeOfBusiness', function(businessId, citizenId)
    return Employees.IsEmployeeOfBusiness(businessId, citizenId)
end)

exports('getEmployeeGrade', function(businessId, citizenId)
    return Employees.GetEmployeeGrade(businessId, citizenId)
end)

exports('refreshEmployeeCache', function(businessId)
    return Employees.RefreshCache(businessId)
end)

-- Employee management callbacks
lib.callback.register('advance-manager:getBusinessEmployees', function(source, businessId)
    local src = source
    local Player = QBCore.Functions.GetPlayer(src)
    
    if not Player or not Business.IsBoss(Player.PlayerData.citizenid, businessId) then
        return false
    end
    
    return Employees.GetAll(businessId)
end)

lib.callback.register('advance-manager:hireEmployee', function(source, businessId, targetId, grade, wage)
    local src = source
    local Player = QBCore.Functions.GetPlayer(src)
    local TargetPlayer = QBCore.Functions.GetPlayer(targetId)
    
    if not Player or not TargetPlayer then
        return false, 'Player not found'
    end
    
    if not Business.IsBoss(Player.PlayerData.citizenid, businessId) then
        return false, 'No permission'
    end
    
    return Employees.Hire(businessId, TargetPlayer.PlayerData.citizenid, grade, wage)
end)

lib.callback.register('advance-manager:fireEmployee', function(source, businessId, citizenId)
    local src = source
    local Player = QBCore.Functions.GetPlayer(src)
    
    if not Player or not Business.IsBoss(Player.PlayerData.citizenid, businessId) then
        return false, 'No permission'
    end
    
    return Employees.Fire(businessId, citizenId)
end)

lib.callback.register('advance-manager:updateEmployeeWage', function(source, businessId, citizenId, newWage)
    local src = source
    local Player = QBCore.Functions.GetPlayer(src)
    
    if not Player or not Business.IsBoss(Player.PlayerData.citizenid, businessId) then
        return false
    end
    
    return Employees.UpdateWage(businessId, citizenId, newWage)
end)

lib.callback.register('advance-manager:updateEmployeeGrade', function(source, businessId, citizenId, newGrade)
    local src = source
    local Player = QBCore.Functions.GetPlayer(src)
    
    if not Player or not Business.IsBoss(Player.PlayerData.citizenid, businessId) then
        return false
    end
    
    return Employees.UpdateGrade(businessId, citizenId, newGrade)
end)

lib.callback.register('advance-manager:getPlayerBusiness', function(source)
    local src = source
    local Player = QBCore.Functions.GetPlayer(src)
    
    if not Player then
        return nil
    end
    
    -- Check if player owns a business
    local ownedBusinesses = Business.GetByOwner(Player.PlayerData.citizenid)
    if #ownedBusinesses > 0 then
        return ownedBusinesses[1]
    end
    
    -- Check if player works for a business
    local business = Business.GetByJob(Player.PlayerData.job.name)
    if business then
        return business
    end
    
    return nil
end)

lib.callback.register('advance-manager:getAvailableJobs', function(source)
    local jobs = {}
    
    for jobName, jobData in pairs(QBCore.Shared.Jobs) do
        table.insert(jobs, {
            name = jobName,
            label = jobData.label,
            grades = jobData.grades
        })
    end
    
    return jobs
end)

lib.callback.register('advance-manager:depositFunds', function(source, businessId, amount)
    local src = source
    local Player = QBCore.Functions.GetPlayer(src)

    if not Player then
        return false, 'Player not found'
    end

    if not Business.IsBoss(Player.PlayerData.citizenid, businessId) then
        return false, 'No permission'
    end

    amount = round(amount or 0)
    if amount <= 0 then
        return false, 'Invalid amount'
    end

    -- Check if player has enough money
    local playerMoney = Player.Functions.GetMoney('cash')
    if playerMoney < amount then
        return false, 'Insufficient funds'
    end
    
    -- Remove money from player
    if Player.Functions.RemoveMoney('cash', amount) then
        -- Add money to business
        if Business.UpdateFunds(businessId, amount, false) then
            return true, 'Funds deposited successfully'
        else
            -- If business update fails, return money to player
            Player.Functions.AddMoney('cash', amount)
            return false, 'Failed to deposit funds'
        end
    else
        return false, 'Failed to remove money from player'
    end
end)

lib.callback.register('advance-manager:withdrawFunds', function(source, businessId, amount)
    local src = source
    local Player = QBCore.Functions.GetPlayer(src)

    if not Player then
        return false, 'Player not found'
    end

    if not Business.IsBoss(Player.PlayerData.citizenid, businessId) then
        return false, 'No permission'
    end

    amount = round(amount or 0)
    if amount <= 0 then
        return false, 'Invalid amount'
    end

    -- Check if business has enough money
    local businessFunds = Business.GetFunds(businessId)
    if businessFunds < amount then
        return false, 'Insufficient business funds'
    end
    
    -- Remove money from business
    if Business.UpdateFunds(businessId, amount, true) then
        -- Add money to player
        Player.Functions.AddMoney('cash', amount)
        return true, 'Funds withdrawn successfully'
    else
        return false, 'Failed to withdraw funds'
    end
end)

lib.callback.register('advance-manager:getBusinessFunds', function(source, businessId)
    local src = source
    local Player = QBCore.Functions.GetPlayer(src)
    
    if not Player then
        return false
    end
    
    if not Business.IsBoss(Player.PlayerData.citizenid, businessId) then
        return false
    end
    
    return Business.GetFunds(businessId)
end)

-- Server events
RegisterNetEvent('advance-manager:createBusinessFromClient', function(name, ownerId, jobName, funds)
    local src = source
    
    -- Verify admin permission
    if not QBCore.Functions.HasPermission(src, 'admin') then
        TriggerClientEvent('ox_lib:notify', src, {
            title = 'Error',
            description = 'You do not have permission to create businesses',
            type = 'error'
        })
        return
    end
    
    local targetPlayer = QBCore.Functions.GetPlayer(ownerId)
    if not targetPlayer then
        TriggerClientEvent('ox_lib:notify', src, {
            title = 'Error',
            description = 'Player not found',
            type = 'error'
        })
        return
    end
    
    local success, result = Business.Create(name, targetPlayer.PlayerData.citizenid, jobName, funds or 0)
    
    if success then
        TriggerClientEvent('ox_lib:notify', src, {
            title = 'Success',
            description = 'Business created successfully',
            type = 'success'
        })
        
        TriggerClientEvent('ox_lib:notify', ownerId, {
            title = 'Business Created',
            description = 'You are now the owner of ' .. name,
            type = 'success'
        })
    else
        TriggerClientEvent('ox_lib:notify', src, {
            title = 'Error',
            description = result,
            type = 'error'
        })
    end
end)

print('[advance-manager] Server initialized successfully')

