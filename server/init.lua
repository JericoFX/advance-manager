QBCore = exports['qb-core']:GetCoreObject()

-- Initialize server-side cache for employees (more secure than GlobalState)
local EmployeeCache = {}
local deepClone = lib.table.deepclone
local round = lib.math.round

-- Load modules
local Business = require 'server.modules.business'
local Employees = require 'server.modules.employees'

-- PR-MERGE: harden-business-permissions
local Cooldowns = {}
local COOLDOWN_INTERVALS = {
    getBusinessEmployees = 500,
    hireEmployee = 1000,
    fireEmployee = 1000,
    updateEmployeeWage = 1000,
    updateEmployeeGrade = 1000,
    depositFunds = 1000,
    withdrawFunds = 1000,
    getBusinessFunds = 500,
    createBusinessFromClient = 2000
}

local function getTimeMs()
    if GetGameTimer then
        return GetGameTimer()
    end

    return math.floor(os.clock() * 1000)
end

local function checkCooldown(source, action)
    local interval = COOLDOWN_INTERVALS[action]
    if not interval then
        return true
    end

    local now = getTimeMs()
    local playerCooldowns = Cooldowns[source]
    if not playerCooldowns then
        playerCooldowns = {}
        Cooldowns[source] = playerCooldowns
    end

    local nextAllowed = playerCooldowns[action] or 0
    if now < nextAllowed then
        return false
    end

    playerCooldowns[action] = now + interval
    return true
end

AddEventHandler('playerDropped', function()
    Cooldowns[source] = nil
end)

local function hasBusinessAdminAccess(src)
    if type(src) ~= 'number' or src < 0 then
        return false, 'Invalid source'
    end

    if src == 0 then
        return true
    end

    if QBCore.Functions.HasPermission(src, 'god') or QBCore.Functions.HasPermission(src, 'admin') then
        return true
    end

    local playerId = tostring(src)
    if IsPlayerAceAllowed(playerId, 'advance-manager.admin') then
        return true
    end

    return false, 'You do not have permission to perform this action'
end

local function hasBossAccessToBusiness(Player, businessId)
    if not Player then
        return false
    end

    local business = Business.GetById(businessId)
    if not business then
        return false
    end

    local citizenId = Player.PlayerData and Player.PlayerData.citizenid
    if not citizenId then
        return false
    end

    if business.owner == citizenId then
        return true
    end

    if Player.PlayerData.job.name ~= business.job_name then
        return false
    end

    if not Employees.IsEmployeeOfBusiness(businessId, citizenId) then
        return false
    end

    local jobInfo = Business.GetJobInfo(business.job_name)
    if not jobInfo then
        return false
    end

    local grade = Player.PlayerData.job.grade.level
    local gradeData = jobInfo.grades and jobInfo.grades[tostring(grade)]

    return gradeData and gradeData.isboss or false
end

-- Implements: IDEA-01 – server-side schema validation for business actions
-- Implements: IDEA-02 – enforce authorization checks for business actions
-- Implements: IDEA-03 – rate limiting for sensitive events
local function normalizeBusinessId(businessId)
    local numericId = tonumber(businessId)
    if not numericId or numericId <= 0 then
        return nil
    end

    return math.floor(numericId)
end

local function normalizeCitizenId(citizenId)
    if type(citizenId) ~= 'string' then
        return nil
    end

    local sanitized = citizenId:match('^%s*(.-)%s*$')
    if sanitized == '' then
        return nil
    end

    return sanitized
end

local function normalizeAmount(amount)
    local numericAmount = tonumber(amount)
    if not numericAmount then
        return nil
    end

    return round(numericAmount)
end

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
    local allowed, message = hasBusinessAdminAccess(source)
    if not allowed then
        if source > 0 then
            TriggerClientEvent('ox_lib:notify', source, {
                title = 'Error',
                description = message,
                type = 'error'
            })
        else
            lib.print.error('[advance-manager] createbusiness command rejected: ' .. (message or 'no permission'))
        end
        return
    end

    if not args.name or not args.owner or not args.jobName then
        if source > 0 then
            TriggerClientEvent('advance-manager:client:openCreateBusinessMenu', source)
        else
            lib.print.warn('[advance-manager] Console usage of /createbusiness requires all parameters.')
        end
        return
    end

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

lib.addCommand('businessmenu', {
    help = 'Open business management menu'
}, function(source)
    if source <= 0 then
        lib.print.warn('[advance-manager] Console cannot open the business management menu.')
        return
    end

    local Player = QBCore.Functions.GetPlayer(source)
    if not Player then
        return
    end

    TriggerClientEvent('advance-manager:client:openBusinessManagementMenu', source)
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
    return GetEmployeeCache()
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
    if not checkCooldown(src, 'getBusinessEmployees') then
        return false
    end

    local normalizedBusinessId = normalizeBusinessId(businessId)
    if not normalizedBusinessId then
        return false
    end

    local Player = QBCore.Functions.GetPlayer(src)
    
    if not hasBossAccessToBusiness(Player, normalizedBusinessId) then
        return false
    end
    
    return Employees.GetAll(normalizedBusinessId)
end)

lib.callback.register('advance-manager:hireEmployee', function(source, businessId, targetId, grade, wage)
    local src = source
    if not checkCooldown(src, 'hireEmployee') then
        return false, 'Please wait before hiring another employee'
    end

    local normalizedBusinessId = normalizeBusinessId(businessId)
    local normalizedTargetId = tonumber(targetId)
    if not normalizedBusinessId or not normalizedTargetId or normalizedTargetId <= 0 then
        return false, 'Invalid request'
    end

    local numericGrade = tonumber(grade)
    local numericWage = tonumber(wage)
    if not numericGrade or not numericWage or numericWage < 0 then
        return false, 'Invalid request'
    end

    local Player = QBCore.Functions.GetPlayer(src)
    local TargetPlayer = QBCore.Functions.GetPlayer(normalizedTargetId)
    
    if not Player or not TargetPlayer then
        return false, 'Player not found'
    end
    
    if not hasBossAccessToBusiness(Player, normalizedBusinessId) then
        return false, 'No permission'
    end
    
    return Employees.Hire(normalizedBusinessId, TargetPlayer.PlayerData.citizenid, numericGrade, numericWage)
end)

lib.callback.register('advance-manager:fireEmployee', function(source, businessId, citizenId)
    local src = source
    if not checkCooldown(src, 'fireEmployee') then
        return false, 'Please wait before firing another employee'
    end

    local normalizedBusinessId = normalizeBusinessId(businessId)
    local normalizedCitizenId = normalizeCitizenId(citizenId)
    if not normalizedBusinessId or not normalizedCitizenId then
        return false, 'Invalid request'
    end

    local Player = QBCore.Functions.GetPlayer(src)
    
    if not hasBossAccessToBusiness(Player, normalizedBusinessId) then
        return false, 'No permission'
    end
    
    return Employees.Fire(normalizedBusinessId, normalizedCitizenId)
end)

lib.callback.register('advance-manager:updateEmployeeWage', function(source, businessId, citizenId, newWage)
    local src = source
    if not checkCooldown(src, 'updateEmployeeWage') then
        return false
    end

    local normalizedBusinessId = normalizeBusinessId(businessId)
    local normalizedCitizenId = normalizeCitizenId(citizenId)
    local normalizedWage = tonumber(newWage)
    if not normalizedBusinessId or not normalizedCitizenId or not normalizedWage or normalizedWage < 0 then
        return false
    end

    local Player = QBCore.Functions.GetPlayer(src)
    
    if not hasBossAccessToBusiness(Player, normalizedBusinessId) then
        return false
    end
    
    return Employees.UpdateWage(normalizedBusinessId, normalizedCitizenId, normalizedWage)
end)

lib.callback.register('advance-manager:updateEmployeeGrade', function(source, businessId, citizenId, newGrade)
    local src = source
    if not checkCooldown(src, 'updateEmployeeGrade') then
        return false
    end

    local normalizedBusinessId = normalizeBusinessId(businessId)
    local normalizedCitizenId = normalizeCitizenId(citizenId)
    local normalizedGrade = tonumber(newGrade)
    if not normalizedBusinessId or not normalizedCitizenId or normalizedGrade == nil then
        return false
    end

    local Player = QBCore.Functions.GetPlayer(src)
    
    if not hasBossAccessToBusiness(Player, normalizedBusinessId) then
        return false
    end
    
    return Employees.UpdateGrade(normalizedBusinessId, normalizedCitizenId, normalizedGrade)
end)

local function enrichBusinessPayload(business)
    if not business then
        return nil
    end

    local jobInfo = Business.GetJobInfo(business.job_name)
    if jobInfo then
        local jobInfoPayload = deepClone(jobInfo)
        business.jobInfo = jobInfoPayload
        business.job_info = jobInfoPayload

        local gradeMetadata = Employees.GetGradeMetadata(jobInfo)
        if gradeMetadata and next(gradeMetadata) then
            local gradePayload = deepClone(gradeMetadata)
            business.gradeMetadata = gradePayload
            business.grade_metadata = gradePayload
        end
    end

    local minWage, maxWage = Employees.GetWageLimits()
    business.wageLimits = {min = minWage, max = maxWage}
    business.wage_limits = deepClone(business.wageLimits)

    local cachedEmployees = Employees.GetFromCache(business.id)
    if cachedEmployees then
        business.employee_count = #cachedEmployees
    else
        business.employee_count = 0
    end

    return business
end

lib.callback.register('advance-manager:getPlayerBusiness', function(source)
    local src = source
    local Player = QBCore.Functions.GetPlayer(src)

    if not Player then
        return nil
    end
    
    -- Check if player owns a business
    local ownedBusinesses = Business.GetByOwner(Player.PlayerData.citizenid)
    if #ownedBusinesses > 0 then
        return enrichBusinessPayload(ownedBusinesses[1])
    end

    -- Check if player works for a business
    local business = Business.GetByJob(Player.PlayerData.job.name)
    if business then
        if not Employees.IsEmployeeOfBusiness(business.id, Player.PlayerData.citizenid) then
            return nil
        end

        return enrichBusinessPayload(business)
    end

    return nil
end)

lib.callback.register('advance-manager:canCreateBusiness', function(source)
    if source <= 0 then
        return false, 'This action is only available in-game'
    end

    local Player = QBCore.Functions.GetPlayer(source)
    if not Player then
        return false, 'Player not found'
    end

    local allowed, message = hasBusinessAdminAccess(source)
    if not allowed then
        return false, message
    end

    return true
end)

lib.callback.register('advance-manager:getAvailableJobs', function(source)
    if source <= 0 then
        return false, 'This action is only available in-game'
    end

    local allowed, message = hasBusinessAdminAccess(source)
    if not allowed then
        return false, message
    end

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
    if not checkCooldown(src, 'depositFunds') then
        return false, 'Please wait before making another deposit'
    end

    local normalizedBusinessId = normalizeBusinessId(businessId)
    local normalizedAmount = normalizeAmount(amount)
    if not normalizedBusinessId or not normalizedAmount then
        return false, 'Invalid amount'
    end

    local Player = QBCore.Functions.GetPlayer(src)

    if not Player then
        return false, 'Player not found'
    end

    if not hasBossAccessToBusiness(Player, normalizedBusinessId) then
        return false, 'No permission'
    end

    if normalizedAmount <= 0 then
        return false, 'Invalid amount'
    end

    -- Check if player has enough money
    local playerMoney = Player.Functions.GetMoney('cash')
    if playerMoney < normalizedAmount then
        return false, 'Insufficient funds'
    end
    
    -- Remove money from player
    if Player.Functions.RemoveMoney('cash', normalizedAmount) then
        -- Add money to business
        if Business.UpdateFunds(normalizedBusinessId, normalizedAmount, false) then
            return true, 'Funds deposited successfully'
        else
            -- If business update fails, return money to player
            Player.Functions.AddMoney('cash', normalizedAmount)
            return false, 'Failed to deposit funds'
        end
    else
        return false, 'Failed to remove money from player'
    end
end)

lib.callback.register('advance-manager:withdrawFunds', function(source, businessId, amount)
    local src = source
    if not checkCooldown(src, 'withdrawFunds') then
        return false, 'Please wait before making another withdrawal'
    end

    local normalizedBusinessId = normalizeBusinessId(businessId)
    local normalizedAmount = normalizeAmount(amount)
    if not normalizedBusinessId or not normalizedAmount then
        return false, 'Invalid amount'
    end

    local Player = QBCore.Functions.GetPlayer(src)

    if not Player then
        return false, 'Player not found'
    end

    if not hasBossAccessToBusiness(Player, normalizedBusinessId) then
        return false, 'No permission'
    end

    if normalizedAmount <= 0 then
        return false, 'Invalid amount'
    end

    -- Remove money from business (atomic)
    if Business.WithdrawFunds(normalizedBusinessId, normalizedAmount) then
        -- Add money to player
        if Player.Functions.AddMoney('cash', normalizedAmount) then
            return true, 'Funds withdrawn successfully'
        end

        local rollback = Business.UpdateFunds(normalizedBusinessId, normalizedAmount, false)
        if not rollback then
            lib.print.error(('[advance-manager] Failed to rollback withdrawal for business %s'):format(normalizedBusinessId))
        end

        return false, 'Failed to add money to player'
    else
        return false, 'Insufficient business funds'
    end
end)

lib.callback.register('advance-manager:getBusinessFunds', function(source, businessId)
    local src = source
    if not checkCooldown(src, 'getBusinessFunds') then
        return false
    end

    local normalizedBusinessId = normalizeBusinessId(businessId)
    if not normalizedBusinessId then
        return false
    end

    local Player = QBCore.Functions.GetPlayer(src)
    
    if not Player then
        return false
    end
    
    if not hasBossAccessToBusiness(Player, normalizedBusinessId) then
        return false
    end
    
    return Business.GetFunds(normalizedBusinessId)
end)

-- Server events
RegisterNetEvent('advance-manager:createBusinessFromClient', function(name, ownerId, jobName, funds)
    local src = source

    if not checkCooldown(src, 'createBusinessFromClient') then
        TriggerClientEvent('ox_lib:notify', src, {
            title = 'Error',
            description = 'Please wait before creating another business',
            type = 'error'
        })
        return
    end

    if not QBCore.Functions.GetPlayer(src) then
        return
    end

    local allowed, message = hasBusinessAdminAccess(src)
    if not allowed then
        TriggerClientEvent('ox_lib:notify', src, {
            title = 'Error',
            description = message or 'You do not have permission to create businesses',
            type = 'error'
        })
        return
    end

    local sanitizedName = type(name) == 'string' and name:gsub('%s+', ' '):gsub('^%s*(.-)%s*$', '%1') or nil
    if not sanitizedName or sanitizedName == '' then
        TriggerClientEvent('ox_lib:notify', src, {
            title = 'Error',
            description = 'A business name is required',
            type = 'error'
        })
        return
    end

    if #sanitizedName > 120 then
        TriggerClientEvent('ox_lib:notify', src, {
            title = 'Error',
            description = 'Business name is too long',
            type = 'error'
        })
        return
    end

    local parsedOwnerId = tonumber(ownerId)
    if not parsedOwnerId then
        TriggerClientEvent('ox_lib:notify', src, {
            title = 'Error',
            description = 'Invalid owner ID',
            type = 'error'
        })
        return
    end

    local targetPlayer = QBCore.Functions.GetPlayer(parsedOwnerId)
    if not targetPlayer then
        TriggerClientEvent('ox_lib:notify', src, {
            title = 'Error',
            description = 'Player not found',
            type = 'error'
        })
        return
    end

    local jobKey = type(jobName) == 'string' and jobName or nil
    if jobKey and not QBCore.Shared.Jobs[jobKey] and jobKey:lower() ~= jobKey then
        local lower = jobKey:lower()
        if QBCore.Shared.Jobs[lower] then
            jobKey = lower
        end
    end

    if not jobKey or not QBCore.Shared.Jobs[jobKey] then
        TriggerClientEvent('ox_lib:notify', src, {
            title = 'Error',
            description = 'Invalid job name',
            type = 'error'
        })
        return
    end

    local startingFunds = normalizeAmount(funds) or 0
    if startingFunds < 0 then
        TriggerClientEvent('ox_lib:notify', src, {
            title = 'Error',
            description = 'Starting funds cannot be negative',
            type = 'error'
        })
        return
    end

    local success, result = Business.Create(sanitizedName, targetPlayer.PlayerData.citizenid, jobKey, startingFunds)

    if success then
        TriggerClientEvent('ox_lib:notify', src, {
            title = 'Success',
            description = 'Business created successfully',
            type = 'success'
        })

        TriggerClientEvent('ox_lib:notify', parsedOwnerId, {
            title = 'Business Created',
            description = 'You are now the owner of ' .. sanitizedName,
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
