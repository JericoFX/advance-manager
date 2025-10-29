local Employees = {}
local Business = require 'server.modules.business'

local clamp = lib.math.clamp
local round = lib.math.round
local contains = lib.table.contains
local deepClone = lib.table.deepclone

local MIN_WAGE, MAX_WAGE = 0, 10000

function Employees.GetWageLimits()
    return MIN_WAGE, MAX_WAGE
end

local function normalizeCharinfo(rawCharinfo)
    local decoded = {}

    if type(rawCharinfo) == 'table' then
        decoded = rawCharinfo
    else
        local ok, parsed = pcall(json.decode, rawCharinfo or '{}')
        if ok and type(parsed) == 'table' then
            decoded = parsed
        end
    end

    local firstname = decoded.firstname
    if type(firstname) == 'string' then
        firstname = firstname:match('^%s*(.-)%s*$')
    end
    if type(firstname) ~= 'string' or firstname == '' then
        firstname = 'Unknown'
    end

    local lastname = decoded.lastname
    if type(lastname) == 'string' then
        lastname = lastname:match('^%s*(.-)%s*$')
    end
    if type(lastname) ~= 'string' or lastname == '' then
        lastname = 'Unknown'
    end

    decoded.firstname = firstname
    decoded.lastname = lastname
    decoded.fullname = firstname .. ' ' .. lastname

    return deepClone(decoded)
end

local function sanitizeWage(wage)
    return clamp(round(wage or MIN_WAGE), MIN_WAGE, MAX_WAGE)
end

local function extractGrades(jobInfo)
    local grades = {}
    local minGrade, maxGrade = math.huge, -math.huge

    for gradeKey in pairs(jobInfo.grades) do
        local numericGrade = tonumber(gradeKey)

        if numericGrade then
            grades[#grades + 1] = numericGrade
            if numericGrade < minGrade then
                minGrade = numericGrade
            end

            if numericGrade > maxGrade then
                maxGrade = numericGrade
            end
        end
    end

    if minGrade == math.huge then
        minGrade, maxGrade = 0, 0
    end

    return grades, minGrade, maxGrade
end

local function sanitizeGrade(jobInfo, grade)
    local numericGrade = round(grade or 0)
    local gradeSet, minGrade, maxGrade = extractGrades(jobInfo)
    numericGrade = clamp(numericGrade, minGrade, maxGrade)

    if not contains(gradeSet, numericGrade) then
        return nil
    end

    return numericGrade
end

function Employees.GetGradeMetadata(jobInfo)
    local metadata = {}

    if type(jobInfo) ~= 'table' or type(jobInfo.grades) ~= 'table' then
        return metadata
    end

    for gradeKey, gradeData in pairs(jobInfo.grades) do
        local numericGrade = tonumber(gradeKey)
        if numericGrade then
            metadata[#metadata + 1] = {
                value = numericGrade,
                label = gradeData.label or gradeData.name or ('Grade ' .. numericGrade),
                wage = tonumber(gradeData.payment),
                isboss = gradeData.isboss and true or false
            }
        end
    end

    table.sort(metadata, function(a, b)
        return a.value < b.value
    end)

    return metadata
end

-- Función para cargar todos los empleados al caché
function Employees.LoadAllToCache()
    local result = MySQL.query.await([[
        SELECT be.*, p.charinfo, b.name as business_name, b.job_name
        FROM business_employees be
        LEFT JOIN players p ON p.citizenid = be.citizenid
        LEFT JOIN businesses b ON b.id = be.business_id
        ORDER BY be.business_id, be.grade DESC
    ]])
    
    local cache = {}
    if result then
        for _, employee in pairs(result) do
            local businessId = tostring(employee.business_id)
            if not cache[businessId] then
                cache[businessId] = {}
            end
            
            local charinfo = normalizeCharinfo(employee.charinfo)
            table.insert(cache[businessId], {
                id = employee.id,
                citizenid = employee.citizenid,
                grade = employee.grade,
                wage = employee.wage,
                name = charinfo.fullname,
                full_name = charinfo.fullname,
                business_name = employee.business_name,
                job_name = employee.job_name,
                charinfo = deepClone(charinfo),
                last_updated = os.time()
            })
        end
    end
    
    -- Use server-side cache instead of GlobalState for security
    Employees.SetCache(cache)
    print('[advance-manager] Loaded ' .. (result and #result or 0) .. ' employees to secure server cache')
end

-- Esta función se define en el init.lua y se asigna dinámicamente
-- Se mantiene aquí como placeholder para documentación

-- Función para actualizar el caché de un negocio específico
function Employees.RefreshCache(businessId)
    local result = MySQL.query.await([[
        SELECT be.*, p.charinfo, b.name as business_name, b.job_name
        FROM business_employees be
        LEFT JOIN players p ON p.citizenid = be.citizenid
        LEFT JOIN businesses b ON b.id = be.business_id
        WHERE be.business_id = ?
        ORDER BY be.grade DESC
    ]], {businessId})
    
    local businessIdStr = tostring(businessId)
    local employees = {}
    
    if result then
        for _, employee in pairs(result) do
            local charinfo = normalizeCharinfo(employee.charinfo)
            table.insert(employees, {
                id = employee.id,
                citizenid = employee.citizenid,
                grade = employee.grade,
                wage = employee.wage,
                name = charinfo.fullname,
                full_name = charinfo.fullname,
                business_name = employee.business_name,
                job_name = employee.job_name,
                charinfo = deepClone(charinfo),
                last_updated = os.time()
            })
        end
    end
    
    -- Use server-side cache instead of GlobalState for security
    Employees.SetInCache(businessId, employees)
    return employees
end

-- Función para obtener un empleado específico por negocio y citizen
function Employees.GetByBusinessAndCitizen(businessId, citizenId)
    local employees = Employees.GetFromCache(businessId)
    for _, employee in pairs(employees) do
        if employee.citizenid == citizenId then
            return employee
        end
    end
    return nil
end

-- Función para verificar si un ciudadano es empleado de un negocio
function Employees.IsEmployeeOfBusiness(businessId, citizenId)
    local employee = Employees.GetByBusinessAndCitizen(businessId, citizenId)
    return employee ~= nil
end

-- Función para obtener el grado de un empleado
function Employees.GetEmployeeGrade(businessId, citizenId)
    local employee = Employees.GetByBusinessAndCitizen(businessId, citizenId)
    return employee and employee.grade or 0
end

function Employees.Hire(businessId, citizenId, grade, wage)
    local business = Business.GetById(businessId)
    if not business then
        return false, 'Business not found'
    end
    
    local jobInfo = Business.GetJobInfo(business.job_name)
    if not jobInfo then
        return false, 'Job not found'
    end
    
    local sanitizedGrade = sanitizeGrade(jobInfo, grade)
    if not sanitizedGrade then
        return false, 'Invalid grade'
    end
    
    -- Check if already employed
    local existing = MySQL.query.await('SELECT id FROM business_employees WHERE business_id = ? AND citizenid = ?', {businessId, citizenId})
    if existing and existing[1] then
        return false, 'Employee already hired'
    end
    
    -- Set job for player
    local Player = QBCore.Functions.GetPlayerByCitizenId(citizenId)
    if Player then
        Player.Functions.SetJob(business.job_name, sanitizedGrade)
    end

    -- Add to database
    local result = MySQL.insert.await([[
        INSERT INTO business_employees (business_id, citizenid, grade, wage)
        VALUES (?, ?, ?, ?)
    ]], {businessId, citizenId, sanitizedGrade, sanitizeWage(wage)})
    
    if result then
        -- Refresh cache for this business
        Employees.RefreshCache(businessId)
        return true, 'Employee hired successfully'
    else
        return false, 'Failed to hire employee'
    end
end

function Employees.Fire(businessId, citizenId)
    local business = Business.GetById(businessId)
    if not business then
        return false, 'Business not found'
    end
    
    -- Set job to unemployed
    local Player = QBCore.Functions.GetPlayerByCitizenId(citizenId)
    if Player then
        Player.Functions.SetJob('unemployed', 0)
    end
    
    -- Remove from database
    local result = MySQL.update.await('DELETE FROM business_employees WHERE business_id = ? AND citizenid = ?', {businessId, citizenId})
    
    if result > 0 then
        -- Refresh cache for this business
        Employees.RefreshCache(businessId)
        return true, 'Employee fired successfully'
    else
        return false, 'Employee not found'
    end
end

function Employees.GetAll(businessId)
    local result = MySQL.query.await([[
        SELECT be.*, p.charinfo
        FROM business_employees be
        LEFT JOIN players p ON p.citizenid = be.citizenid
        WHERE be.business_id = ?
    ]], {businessId})
    
    local employees = {}
    if result then
        for _, employee in pairs(result) do
            local charinfo = normalizeCharinfo(employee.charinfo)
            table.insert(employees, {
                id = employee.id,
                citizenid = employee.citizenid,
                grade = employee.grade,
                wage = employee.wage,
                name = charinfo.fullname,
                full_name = charinfo.fullname,
                charinfo = deepClone(charinfo)
            })
        end
    end

    return employees
end

function Employees.UpdateWage(businessId, citizenId, newWage)
    local sanitizedWage = sanitizeWage(newWage)
    local result = MySQL.update.await([[
        UPDATE business_employees
        SET wage = ?
        WHERE business_id = ? AND citizenid = ?
    ]], {sanitizedWage, businessId, citizenId})
    
    if result > 0 then
        -- Refresh cache for this business
        Employees.RefreshCache(businessId)
        return true
    else
        return false
    end
end

function Employees.UpdateGrade(businessId, citizenId, newGrade)
    local business = Business.GetById(businessId)
    if not business then
        return false, 'Business not found'
    end

    local jobInfo = Business.GetJobInfo(business.job_name)
    local sanitizedGrade = jobInfo and sanitizeGrade(jobInfo, newGrade)
    if not sanitizedGrade then
        return false, 'Invalid grade'
    end

    -- Update player job grade
    local Player = QBCore.Functions.GetPlayerByCitizenId(citizenId)
    if Player then
        Player.Functions.SetJob(business.job_name, sanitizedGrade)
    end

    -- Update database
    local result = MySQL.update.await([[
        UPDATE business_employees
        SET grade = ?
        WHERE business_id = ? AND citizenid = ?
    ]], {sanitizedGrade, businessId, citizenId})
    
    if result > 0 then
        -- Refresh cache for this business
        Employees.RefreshCache(businessId)
        return true
    else
        return false
    end
end

return Employees
