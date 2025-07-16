local Business = {}

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
        grades = job.grades,
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

function Business.UpdateFunds(businessId, amount)
    local result = MySQL.update.await('UPDATE businesses SET funds = funds + ? WHERE id = ?', {amount, businessId})
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
    
    if gradeData.isboss then
        return true
    end
    
    return false
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
