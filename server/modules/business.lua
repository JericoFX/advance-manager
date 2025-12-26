local Business = {}
local deepClone = lib.table.deepclone

local JobPermissionCache = {}
local PermissionMatrixCache = {}

local function normalizePermissionList(list)
    local normalized = {}

    if type(list) ~= 'table' then
        if type(list) == 'string' and list ~= '' then
            normalized[list] = true
        end

        return normalized
    end

    for key, value in pairs(list) do
        if type(key) == 'number' then
            if type(value) == 'string' and value ~= '' then
                normalized[value] = true
            end
        else
            if value == true then
                normalized[key] = true
            elseif type(value) == 'string' and value ~= '' then
                normalized[value] = true
            end
        end
    end

    return normalized
end

local function buildJobPermissionDefaults(jobInfo)
    local jobName = jobInfo and jobInfo.name
    if not jobName then
        return {}
    end

    if JobPermissionCache[jobName] then
        return JobPermissionCache[jobName]
    end

    local defaults = {}

    if type(jobInfo.grades) == 'table' then
        for gradeKey, gradeData in pairs(jobInfo.grades) do
            local gradePermissions = {}

            if type(gradeData.permissions) == 'table' then
                gradePermissions = normalizePermissionList(gradeData.permissions)
            elseif gradeData.permissions == true then
                gradePermissions['*'] = true
            end

            defaults[gradeKey] = gradePermissions
        end
    end

    JobPermissionCache[jobName] = defaults

    return defaults
end

local function buildPermissionMatrix(business, jobInfo)
    local defaults = buildJobPermissionDefaults(jobInfo)
    local matrix = {}

    for gradeKey, permissions in pairs(defaults) do
        matrix[gradeKey] = {}
        for permissionName, allowed in pairs(permissions) do
            matrix[gradeKey][permissionName] = allowed and true or nil
        end
    end

    local metadata = business and business.metadata
    local metadataPermissions = metadata and metadata.permissions

    if type(metadataPermissions) == 'table' then
        for key, value in pairs(metadataPermissions) do
            local numericKey = tonumber(key)
            if numericKey then
                local gradeKey = tostring(numericKey)
                matrix[gradeKey] = matrix[gradeKey] or {}
                local gradePermissions = normalizePermissionList(value)
                for permissionName in pairs(gradePermissions) do
                    matrix[gradeKey][permissionName] = true
                end
            elseif type(value) == 'table' then
                local permissionName = key
                for _, gradeRef in pairs(value) do
                    local gradeKey = tostring(gradeRef)
                    matrix[gradeKey] = matrix[gradeKey] or {}
                    matrix[gradeKey][permissionName] = true
                end
            elseif value == true then
                matrix['*'] = matrix['*'] or {}
                matrix['*'][key] = true
            end
        end
    end

    return matrix
end

local function getPermissionMatrix(business, jobInfo)
    if not business then
        return {}
    end

    local cacheKey = business.id and tostring(business.id)
    local permissions = business.metadata and business.metadata.permissions
    local signature = permissions and json.encode(permissions) or ''

    if cacheKey then
        local cached = PermissionMatrixCache[cacheKey]
        if cached and cached.signature == signature then
            return cached.matrix
        end
    end

    local matrix = buildPermissionMatrix(business, jobInfo)

    if cacheKey then
        PermissionMatrixCache[cacheKey] = {
            signature = signature,
            matrix = matrix
        }
    end

    return matrix
end

local function gradeAllowsPermission(matrix, gradeKey, permissionName)
    if not matrix then
        return false
    end

    if permissionName == '*' then
        return true
    end

    local gradePermissions = matrix[gradeKey]
    if gradePermissions then
        if gradePermissions[permissionName] then
            return true
        end

        if gradePermissions['*'] then
            return true
        end
    end

    local wildcard = matrix['*']
    if wildcard then
        if wildcard[permissionName] then
            return true
        end

        if wildcard['*'] then
            return true
        end
    end

    return false
end

function Business.GetJobInfo(jobName)
    local job = QBCore.Shared.Jobs[jobName]
    if not job then
        return nil
    end
    
    local bossGrade = nil
    for grade, data in pairs(job.grades) do
        if data.isboss then
            bossGrade = tonumber(grade)
            break
        end
    end
    
    return {
        name = jobName,
        label = job.label,
        grades = deepClone(job.grades),
        bossGrade = bossGrade
    }
end

function Business.Create(name, owner, jobName, startingFunds, metadata)
    local jobInfo = Business.GetJobInfo(jobName)
    if not jobInfo then
        return false, 'Job does not exist'
    end
    
    local result = MySQL.insert.await([[
        INSERT INTO businesses (name, owner, job_name, funds, metadata)
        VALUES (?, ?, ?, ?, ?)
    ]], {
        name,
        owner,
        jobName,
        startingFunds or 0,
        json.encode(metadata or {})
    })
    
    if result then
        return true, result
    else
        return false, 'Failed to create business'
    end
end

function Business.GetById(businessId)
    local result = MySQL.query.await('SELECT * FROM businesses WHERE id = ?', {businessId})
    if result and result[1] then
        local business = result[1]
        business.metadata = json.decode(business.metadata or '{}')
        return business
    end
    return nil
end

function Business.GetByJob(jobName)
    local result = MySQL.query.await('SELECT * FROM businesses WHERE job_name = ?', {jobName})
    if result and result[1] then
        local business = result[1]
        business.metadata = json.decode(business.metadata or '{}')
        return business
    end
    return nil
end

function Business.GetByOwner(citizenId)
    local result = MySQL.query.await('SELECT * FROM businesses WHERE owner = ?', {citizenId})
    local businesses = {}
    
    if result then
        for _, business in pairs(result) do
            business.metadata = json.decode(business.metadata or '{}')
            table.insert(businesses, business)
        end
    end
    
    return businesses
end

function Business.UpdateFunds(businessId, amount, isWithdrawal)
    local finalAmount = isWithdrawal and -amount or amount
    local result = MySQL.update.await('UPDATE businesses SET funds = funds + ? WHERE id = ?', {finalAmount, businessId})
    return result > 0
end

function Business.WithdrawFunds(businessId, amount)
    local result = MySQL.update.await('UPDATE businesses SET funds = funds - ? WHERE id = ? AND funds >= ?', {amount, businessId, amount})
    return result > 0
end

function Business.SetFunds(businessId, amount)
    local result = MySQL.update.await('UPDATE businesses SET funds = ? WHERE id = ?', {amount, businessId})
    return result > 0
end

function Business.GetFunds(businessId)
    local result = MySQL.query.await('SELECT funds FROM businesses WHERE id = ?', {businessId})
    if result and result[1] then
        return result[1].funds
    end
    return 0
end

local function normalizePermissionRequest(permission)
    if permission == nil or permission == '' then
        return nil
    end

    if type(permission) == 'table' then
        local normalized = {}
        for _, value in pairs(permission) do
            if type(value) == 'string' and value ~= '' then
                normalized[#normalized + 1] = value
            end
        end
        return #normalized > 0 and normalized or nil
    end

    if type(permission) == 'string' then
        return {permission}
    end

    return nil
end

function Business.HasPermission(citizenId, businessId, permission)
    local Player = QBCore.Functions.GetPlayerByCitizenId(citizenId)
    if not Player then
        return false
    end

    local business = Business.GetById(businessId)
    if not business then
        return false
    end
    
    if business.owner == citizenId then
        return true
    end
    
    if Player.PlayerData.job.name ~= business.job_name then
        return false
    end
    
    local jobInfo = Business.GetJobInfo(business.job_name)
    if not jobInfo then
        return false
    end
    
    local grade = Player.PlayerData.job.grade.level
    local gradeData = jobInfo.grades[tostring(grade)]
    
    if not gradeData then
        return false
    end
    
    if gradeData.isboss and (permission == nil or permission == 'boss') then
        return true
    end

    local requiredPermissions = normalizePermissionRequest(permission)

    if not requiredPermissions then
        return gradeData.isboss == true
    end

    if gradeData.isboss then
        return true
    end

    if gradeData.isboss == false and #requiredPermissions == 1 and requiredPermissions[1] == 'boss' then
        return false
    end

    local permissionMatrix = getPermissionMatrix(business, jobInfo)
    local gradeKey = tostring(grade)

    for _, permissionName in ipairs(requiredPermissions) do
        if permissionName == 'boss' then
            if not gradeData.isboss then
                return false
            end
        elseif not gradeAllowsPermission(permissionMatrix, gradeKey, permissionName) then
            return false
        end
    end

    return true
end

function Business.IsBoss(citizenId, businessId)
    local Player = QBCore.Functions.GetPlayerByCitizenId(citizenId)
    if not Player then
        return false
    end
    
    local business = Business.GetById(businessId)
    if not business then
        return false
    end
    
    if business.owner == citizenId then
        return true
    end
    
    if Player.PlayerData.job.name ~= business.job_name then
        return false
    end
    
    local jobInfo = Business.GetJobInfo(business.job_name)
    if not jobInfo then
        return false
    end
    
    local grade = Player.PlayerData.job.grade.level
    local gradeData = jobInfo.grades[tostring(grade)]
    
    return gradeData and gradeData.isboss or false
end

return Business
