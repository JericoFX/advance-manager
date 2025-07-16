local Employees = {}
local Business = require 'server.modules.business'

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
            
            local charinfo = json.decode(employee.charinfo or '{}')
            table.insert(cache[businessId], {
                id = employee.id,
                citizenid = employee.citizenid,
                grade = employee.grade,
                wage = employee.wage,
                name = charinfo.firstname .. ' ' .. charinfo.lastname,
                business_name = employee.business_name,
                job_name = employee.job_name,
                last_updated = os.time()
            })
        end
    end
    
    GlobalState.BusinessEmployees = cache
    print('[advance-manager] Loaded ' .. (result and #result or 0) .. ' employees to cache')
end

-- Función para obtener empleados del caché
function Employees.GetFromCache(businessId)
    local cache = GlobalState.BusinessEmployees
    return cache[tostring(businessId)] or {}
end

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
    
    local cache = GlobalState.BusinessEmployees
    local businessIdStr = tostring(businessId)
    cache[businessIdStr] = {}
    
    if result then
        for _, employee in pairs(result) do
            local charinfo = json.decode(employee.charinfo or '{}')
            table.insert(cache[businessIdStr], {
                id = employee.id,
                citizenid = employee.citizenid,
                grade = employee.grade,
                wage = employee.wage,
                name = charinfo.firstname .. ' ' .. charinfo.lastname,
                business_name = employee.business_name,
                job_name = employee.job_name,
                last_updated = os.time()
            })
        end
    end
    
    GlobalState.BusinessEmployees = cache
    return cache[businessIdStr]
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
    
    if not jobInfo.grades[tostring(grade)] then
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
        Player.Functions.SetJob(business.job_name, grade)
    end
    
    -- Add to database
    local result = MySQL.insert.await([[
        INSERT INTO business_employees (business_id, citizenid, grade, wage)
        VALUES (?, ?, ?, ?)
    ]], {businessId, citizenId, grade, wage})
    
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
            local charinfo = json.decode(employee.charinfo or '{}')
            table.insert(employees, {
                id = employee.id,
                citizenid = employee.citizenid,
                grade = employee.grade,
                wage = employee.wage,
                name = charinfo.firstname .. ' ' .. charinfo.lastname
            })
        end
    end
    
    return employees
end

function Employees.UpdateWage(businessId, citizenId, newWage)
    local result = MySQL.update.await([[
        UPDATE business_employees 
        SET wage = ? 
        WHERE business_id = ? AND citizenid = ?
    ]], {newWage, businessId, citizenId})
    
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
    if not jobInfo or not jobInfo.grades[tostring(newGrade)] then
        return false, 'Invalid grade'
    end
    
    -- Update player job grade
    local Player = QBCore.Functions.GetPlayerByCitizenId(citizenId)
    if Player then
        Player.Functions.SetJob(business.job_name, newGrade)
    end
    
    -- Update database
    local result = MySQL.update.await([[
        UPDATE business_employees 
        SET grade = ? 
        WHERE business_id = ? AND citizenid = ?
    ]], {newGrade, businessId, citizenId})
    
    if result > 0 then
        -- Refresh cache for this business
        Employees.RefreshCache(businessId)
        return true
    else
        return false
    end
end

return Employees
