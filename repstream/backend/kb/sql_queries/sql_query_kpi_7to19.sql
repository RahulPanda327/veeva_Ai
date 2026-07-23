/*
================================================================================
  KPI 7-19 QUERIES – Veeva RepStream AI Modules
  Target: hub_insight360 schema (Server B)
  Cooked data tables used:
    hub_insight360.insight360_peer_match_dul
    hub_insight360.insight360_objection_handler_dul
    hub_insight360.insight360_active_alerts_dul
    hub_insight360.insight360_hcp_awareness_dul
    hub_insight360.insight360_competitive_intel_dul
    hub_insight360.insight360_payer_access_dul
    hub_insight360.insight360_call_transcripts_dul
================================================================================
*/


/*
================================================================================
  KPI 7 – PEER NETWORK MATCHING + WARM APPROACH RECOMMENDATIONS
  Module: New Writer Identification (extends KPI 5-6)
  Logic:  For each unconverted HCP (Bucket A/B from KPI 5-6), surface the
          peer connector HCP with the highest match % and the pre-approved
          warm approach message the rep should use
================================================================================
*/
SELECT
    pm.HCP_Durable_Id,
    pm.HCP_Full_Name,
    pm.Specialty,
    pm.City_State,
    -- Peer match details
    pm.Peer_Match_Pct,
    pm.Peer_Connector_HCP_Id,
    pm.Peer_Connector_Name,
    pm.Warm_Approach_Text,
    -- Enrich with live HCP context from dim table
    h.Target_Decile_Zenpep,
    h.is_gia_tgt                                            AS Is_GIA_Target,
    h.Segment_Description                                   AS Zenpep_Segment,
    -- Territory context
    tm.Territory_Durable_Id,
    tm.Territory_Code,
    tm.Territory_Name,
    tm.District_Name,
    tm.Region_Name,
    CAST(GETDATE() AS DATE)                                 AS Report_As_Of_Date
FROM hub_insight360.insight360_peer_match_dul pm
-- Enrich with live dim data where available
LEFT JOIN hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting_dul h
       ON h.HCP_Durable_Id = pm.HCP_Durable_Id
LEFT JOIN hub_insight360.vw_account_territory_zenpep_reporting_dul at2
       ON at2.HCP_Durable_Id = pm.HCP_Durable_Id
      AND at2.sales_force = 'Commercial_Sales_Field_Force'
LEFT JOIN hub_insight360.vw_tdim_terr_hierarchy_zenpep_reporting_dul tm
       ON tm.Territory_Durable_Id = at2.Territory_Durable_Id
-- Remove REPLACE to convert percentage string to numeric for sorting
ORDER BY
    CAST(REPLACE(pm.Peer_Match_Pct, '%', '') AS DECIMAL(5,1)) DESC;


/*
================================================================================
  KPI 8 – CALL TRANSCRIPT INGESTION SUMMARY
  Module: Objection Handler
  Logic:  Aggregate ingested transcripts by territory and tone to give
          manager/rep a summary view of what conversations are happening
================================================================================
*/
SELECT
    ct.Territory_Durable_Id,
    th.Territory_Name,
    th.District_Name,
    -- Volume metrics
    COUNT(*)                                                AS Total_Transcripts_Ingested,
    COUNT(DISTINCT ct.HCP_Durable_Id)                       AS Unique_HCPs_With_Transcripts,
    COUNT(DISTINCT ct.Src_Call_Id)                          AS Unique_Calls,
    -- Tone breakdown
    SUM(CASE WHEN ct.Transcript_Tone = 'POSITIVE'   THEN 1 ELSE 0 END) AS Positive_Calls,
    SUM(CASE WHEN ct.Transcript_Tone = 'MIXED'      THEN 1 ELSE 0 END) AS Mixed_Calls,
    SUM(CASE WHEN ct.Transcript_Tone = 'OBJECTION'  THEN 1 ELSE 0 END) AS Objection_Calls,
    -- Objection rate
    CAST(
        SUM(CASE WHEN ct.Transcript_Tone = 'OBJECTION' THEN 1.0 ELSE 0 END)
        / NULLIF(COUNT(*), 0) * 100.0
    AS DECIMAL(5,1))                                        AS Objection_Rate_Pct,
    -- Product split
    SUM(CASE WHEN ct.Product_Detailed = 'ZENPEP'    THEN 1 ELSE 0 END) AS Zenpep_Details,
    SUM(CASE WHEN ct.Product_Detailed = 'VOWST'     THEN 1 ELSE 0 END) AS Vowst_Details,
    -- Channel split
    SUM(CASE WHEN ct.Call_Channel = 'F2F'           THEN 1 ELSE 0 END) AS F2F_Calls,
    SUM(CASE WHEN ct.Call_Channel = 'VIRTUAL'       THEN 1 ELSE 0 END) AS Virtual_Calls,
    -- Date range of ingested transcripts
    MIN(CAST(ct.Call_Date AS DATE))                         AS Earliest_Call_Date,
    MAX(CAST(ct.Call_Date AS DATE))                         AS Latest_Call_Date,
    CAST(GETDATE() AS DATE)                                 AS Report_As_Of_Date
FROM hub_insight360.insight360_call_transcripts_dul ct
LEFT JOIN hub_insight360.vw_tdim_terr_hierarchy_zenpep_reporting_dul th
       ON th.Territory_Durable_Id = ct.Territory_Durable_Id
GROUP BY
    ct.Territory_Durable_Id,
    th.Territory_Name,
    th.District_Name
ORDER BY Total_Transcripts_Ingested DESC;


/*
================================================================================
  KPI 9 – NLP OBJECTION ANALYSIS (Frequency + Category Breakdown)
  Module: Objection Handler
  Logic:  Surface the most frequently occurring objection categories
          detected across all transcripts – used to power the
          "Most Common Objection" trend card in the UI
================================================================================
*/
SELECT
    oh.Objection_Category,
    oh.Objection_Frequency_Label,
    -- Aggregate across all instances of this objection category
    COUNT(*)                                                AS Objection_Instance_Count,
    COUNT(DISTINCT oh.HCP_Durable_Id)                       AS Unique_HCPs_Raising_Objection,
    SUM(cast(oh.Call_Count_Mentions as decimal))            AS Total_Call_Mentions,
    -- Detection window
    MIN(oh.Detection_Period)                                AS Earliest_Detection_Period,
    MAX(oh.Detection_Period)                                AS Latest_Detection_Period,
    -- Historical conversion rate (avg across instances of this category)
    CAST(
        AVG(CAST(REPLACE(oh.Historical_Conversion_Rate_Pct, '%', '')
            AS DECIMAL(5,1)))
    AS DECIMAL(5,1))                                        AS Avg_Historical_Conversion_Rate_Pct,
    CAST(GETDATE() AS DATE)                                 AS Report_As_Of_Date
FROM hub_insight360.insight360_objection_handler_dul oh
GROUP BY
    oh.Objection_Category,
    oh.Objection_Frequency_Label
ORDER BY
    Total_Call_Mentions DESC,
    Objection_Instance_Count DESC;


/*
================================================================================
  KPI 10 – OBJECTION CLASSIFICATION DETAIL
  Module: Objection Handler
  Logic:  HCP-level view of each detected objection with full context –
          used to power the objection detail card when rep taps an HCP
================================================================================
*/
SELECT
    oh.Call_Transcript_Id,
    oh.HCP_Durable_Id,
    oh.HCP_Full_Name,
    oh.Call_Date,
    oh.Objection_Category,
    oh.Objection_Frequency_Label,
    oh.Objection_Text,
    oh.Transcript_Summary,
    oh.Call_Count_Mentions,
    oh.Detection_Period,
    oh.Historical_Conversion_Rate_Pct,
    -- MLR response ready flag
    CASE WHEN oh.MLR_Approved_Response IS NOT NULL
         AND oh.MLR_Approved_Response <> ''
         THEN 'YES' ELSE 'NO'
    END                                                     AS MLR_Response_Available,
    oh.MLR_SKU_Code,
    -- Enrich with territory context via call transcripts table
    ct.Territory_Durable_Id,
    th.Territory_Name,
    th.District_Name,
    -- HCP targeting context
    h.Target_Decile_Zenpep,
    h.is_gia_tgt                                            AS Is_GIA_Target,
    h.Specialty_Description,
    h.City_State,
    CAST(GETDATE() AS DATE)                                 AS Report_As_Of_Date
FROM hub_insight360.insight360_objection_handler_dul oh
-- Join to transcripts to get territory
LEFT JOIN hub_insight360.insight360_call_transcripts_dul ct
       ON ct.Src_Call_Id = oh.Call_Transcript_Id
LEFT JOIN hub_insight360.vw_tdim_terr_hierarchy_zenpep_reporting_dul th
       ON th.Territory_Durable_Id = ct.Territory_Durable_Id
-- Enrich HCP context
LEFT JOIN hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting_dul h
       ON h.HCP_Durable_Id = oh.HCP_Durable_Id
ORDER BY
    CAST(oh.Call_Date AS DATE) DESC,
    oh.Call_Count_Mentions DESC;


/*
================================================================================
  KPI 11 – MLR RESPONSE ENGINE
  Module: Objection Handler
  Logic:  For a given objection category, return the pre-approved MLR
          response the rep should use in their next call
          Filter by category in your application layer or use this as-is
          to return all available responses
================================================================================
*/
SELECT
    oh.Objection_Category,
    oh.Objection_Frequency_Label,
    oh.Objection_Text,
    oh.MLR_Approved_Response,
    oh.MLR_SKU_Code,
    oh.Historical_Conversion_Rate_Pct,
    oh.Call_Count_Mentions                                  AS Times_Encountered,
    oh.Detection_Period,
    CAST(GETDATE() AS DATE)                                 AS Report_As_Of_Date
FROM hub_insight360.insight360_objection_handler_dul oh
WHERE oh.MLR_Approved_Response IS NOT NULL
  AND oh.MLR_Approved_Response <> ''
ORDER BY
    -- Highest-frequency objections with MLR responses first
    oh.Call_Count_Mentions DESC,
    oh.Objection_Category;


/*
================================================================================
  KPI 12 – ACTIVE ALERT ANOMALY DETECTION
  Module: Active Alerts
  Logic:  Surface all active AI-detected alerts, prioritised by severity
          Used to power the alert banner and alert list in the RepStream UI
================================================================================
*/
SELECT
    aa.Alert_Id,
    aa.Alert_Priority,
    aa.Alert_Type,
    aa.Alert_Title,
    aa.Detection_Datetime,
    aa.Territory_Durable_Id,
    aa.Territory_Name,
    aa.Affected_HCP_Count,
    aa.Territory_Reach,
    aa.Rx_Risk_Level,
    aa.Counter_Strategy,
    aa.Recommended_Actions,
    -- Enrich with live territory hierarchy
    th.Territory_Code,
    th.District_Name,
    th.Region_Name,
    CAST(GETDATE() AS DATE)                                 AS Report_As_Of_Date
FROM hub_insight360.insight360_active_alerts_dul aa
LEFT JOIN hub_insight360.vw_tdim_terr_hierarchy_zenpep_reporting_dul th
       ON th.Territory_Durable_Id = aa.Territory_Durable_Id
ORDER BY
    CASE aa.Alert_Priority
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH'     THEN 2
        WHEN 'MEDIUM'   THEN 3
        ELSE 4
    END,
    aa.Detection_Datetime DESC;


/*
================================================================================
  KPI 13 – AI IMPACT ANALYSIS (Alert → Rx Risk Quantification)
  Module: Active Alerts
  Logic:  For each active alert, estimate the Rx volume at risk by joining
          to live Rx data for the affected territory
================================================================================
*/
DECLARE @rolling_start DATE = DATEADD(MONTH, -3, CAST(GETDATE() AS DATE));

WITH alert_territory_rx AS (
    SELECT
        aa.Alert_Id,
        aa.Alert_Priority,
        aa.Alert_Title,
        aa.Territory_Durable_Id,
        aa.Territory_Name,
        aa.Rx_Risk_Level,
        aa.Affected_HCP_Count,
        -- Rolling 3M Zenpep TRx for the alerted territory
        SUM(CAST(r.Normalized_Total_Rx_Quantity AS DECIMAL(10,2))) AS Territory_TRx_3M
    FROM hub_insight360.insight360_active_alerts_dul aa
    LEFT JOIN hub_insight360.vw_account_territory_zenpep_reporting_dul at2
           ON at2.Territory_Durable_Id = aa.Territory_Durable_Id
          AND at2.sales_force = 'Commercial_Sales_Field_Force'
    LEFT JOIN hub_insight360.vw_tfact_prescribersales_zenpep_reporting_dul r
           ON r.HCP_Durable_Id = at2.HCP_Durable_Id
          AND r.Brand_Name = 'ZENPEP'
          AND CAST(r.Month_Ending_Date AS DATE) >= @rolling_start
    GROUP BY
        aa.Alert_Id,
        aa.Alert_Priority,
        aa.Alert_Title,
        aa.Territory_Durable_Id,
        aa.Territory_Name,
        aa.Rx_Risk_Level,
        aa.Affected_HCP_Count
)
SELECT
    Alert_Id,
    Alert_Priority,
    Alert_Title,
    Territory_Durable_Id,
    Territory_Name,
    Rx_Risk_Level,
    Affected_HCP_Count,
    Territory_TRx_3M,
    -- Estimated Rx at risk based on risk level
    CAST(
        Territory_TRx_3M *
        CASE Rx_Risk_Level
            WHEN 'High'   THEN 0.20   -- 20% of TRx at risk
            WHEN 'Medium' THEN 0.10
            WHEN 'Low'    THEN 0.05
            ELSE 0.05
        END
    AS DECIMAL(10,2))                                       AS Estimated_TRx_At_Risk,
    CAST(GETDATE() AS DATE)                                 AS Report_As_Of_Date
FROM alert_territory_rx
ORDER BY
    CASE Alert_Priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 ELSE 3 END,
    Estimated_TRx_At_Risk DESC;


/*
================================================================================
  KPI 14 – NEXT BEST ACTION RECOMMENDATIONS
  Module: Active Alerts
  Logic:  For each alert, surface the recommended counter-strategy
          and next best action alongside the top impacted HCPs
================================================================================
*/
SELECT
    aa.Alert_Id,
    aa.Alert_Priority,
    aa.Alert_Title,
    aa.Territory_Name,
    aa.Counter_Strategy,
    aa.Recommended_Actions,
    aa.Affected_HCP_Count,
    aa.Territory_Reach,
    -- Top HCPs in this territory by Zenpep decile for targeting
    STRING_AGG(
        h.Full_Name + ' (Decile: ' + ISNULL(h.Decile, 'N/A') + ')',
        ' | '
    ) WITHIN GROUP (ORDER BY
        TRY_CAST(NULLIF(LTRIM(RTRIM(h.Target_Decile_Sort_Zenpep)),'') AS INT) ASC
    )                                                       AS Top_HCPs_To_Target,
    CAST(GETDATE() AS DATE)                                 AS Report_As_Of_Date
FROM hub_insight360.insight360_active_alerts_dul aa
LEFT JOIN hub_insight360.vw_account_territory_zenpep_reporting_dul at2
       ON at2.Territory_Durable_Id = aa.Territory_Durable_Id
      AND at2.sales_force = 'Commercial_Sales_Field_Force'
LEFT JOIN hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting_dul h
       ON h.HCP_Durable_Id = at2.HCP_Durable_Id
      AND h.Target = 'Y'
GROUP BY
    aa.Alert_Id,
    aa.Alert_Priority,
    aa.Alert_Title,
    aa.Territory_Name,
    aa.Counter_Strategy,
    aa.Recommended_Actions,
    aa.Affected_HCP_Count,
    aa.Territory_Reach
ORDER BY
    CASE aa.Alert_Priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 ELSE 3 END;


/*
================================================================================
  KPI 15 – AVERAGE AWARENESS SCORE TREND
  Module: HCP Awareness
  Logic:  Aggregate awareness scores across all HCPs over 4 measurement
          periods to show the territory-level trend line in the UI
================================================================================
*/
SELECT
    -- Territory context via HCP → territory mapping
    tm.Territory_Durable_Id,
    tm.Territory_Name,
    tm.District_Name,
    -- Average awareness score per measurement period
    CAST(AVG(CAST(REPLACE(aw.Awareness_Score_Jan29, '%', '') AS DECIMAL(5,1)))
        AS DECIMAL(5,1))                                    AS Avg_Awareness_Jan29,
    CAST(AVG(CAST(REPLACE(aw.Awareness_Score_Feb26, '%', '') AS DECIMAL(5,1)))
        AS DECIMAL(5,1))                                    AS Avg_Awareness_Feb26,
    CAST(AVG(CAST(REPLACE(aw.Awareness_Score_Mar25, '%', '') AS DECIMAL(5,1)))
        AS DECIMAL(5,1))                                    AS Avg_Awareness_Mar25,
    CAST(AVG(CAST(REPLACE(aw.Awareness_Score_Apr22, '%', '') AS DECIMAL(5,1)))
        AS DECIMAL(5,1))                                    AS Avg_Awareness_Apr22,
    -- Overall trend direction
    COUNT(DISTINCT aw.HCP_Durable_Id)                       AS HCPs_Tracked,
    SUM(CASE WHEN aw.Trend_Direction = 'Declining'  THEN 1 ELSE 0 END) AS Declining_Count,
    SUM(CASE WHEN aw.Trend_Direction = 'Improving'  THEN 1 ELSE 0 END) AS Improving_Count,
    SUM(CASE WHEN aw.Trend_Direction = 'Stable'     THEN 1 ELSE 0 END) AS Stable_Count,
    CAST(GETDATE() AS DATE)                                 AS Report_As_Of_Date
FROM hub_insight360.insight360_hcp_awareness_dul aw
LEFT JOIN hub_insight360.vw_account_territory_zenpep_reporting_dul at2
       ON at2.HCP_Durable_Id = aw.HCP_Durable_Id
      AND at2.sales_force = 'Commercial_Sales_Field_Force'
LEFT JOIN hub_insight360.vw_tdim_terr_hierarchy_zenpep_reporting_dul tm
       ON tm.Territory_Durable_Id = at2.Territory_Durable_Id
GROUP BY
    tm.Territory_Durable_Id,
    tm.Territory_Name,
    tm.District_Name
ORDER BY Avg_Awareness_Apr22 ASC;  -- Lowest current awareness first = needs most attention


/*
================================================================================
  KPI 16 – NLP ANALYSIS OF NEGATIVELY IMPACTED PRESCRIBERS
  Module: HCP Awareness
  Logic:  HCP-level detail for declining/low awareness HCPs –
          surfaces root cause signals and re-engagement priority
================================================================================
*/
SELECT
    aw.HCP_Durable_Id,
    aw.HCP_Full_Name,
    aw.Specialty,
    aw.City_State,
    -- Awareness trend
    aw.Awareness_Score_Jan29,
    aw.Awareness_Score_Feb26,
    aw.Awareness_Score_Mar25,
    aw.Awareness_Score_Apr22,
    aw.Score_Change_Pct,
    aw.Trend_Direction,
    aw.Root_Cause_Signal,
    aw.Re_Engagement_Priority,
    -- Live HCP targeting context
    h.Target_Decile_Zenpep,
    h.is_gia_tgt                                            AS Is_GIA_Target,
    h.Segment_Description                                   AS Zenpep_Segment,
    -- Territory
    tm.Territory_Durable_Id,
    tm.Territory_Name,
    tm.District_Name,
    CAST(GETDATE() AS DATE)                                 AS Report_As_Of_Date
FROM hub_insight360.insight360_hcp_awareness_dul aw
LEFT JOIN hub_insight360.vw_tdim_healthcarepractitioner_zenpep_reporting_dul h
       ON h.HCP_Durable_Id = aw.HCP_Durable_Id
LEFT JOIN hub_insight360.vw_account_territory_zenpep_reporting_dul at2
       ON at2.HCP_Durable_Id = aw.HCP_Durable_Id
      AND at2.sales_force = 'Commercial_Sales_Field_Force'
LEFT JOIN hub_insight360.vw_tdim_terr_hierarchy_zenpep_reporting_dul tm
       ON tm.Territory_Durable_Id = at2.Territory_Durable_Id
WHERE aw.Trend_Direction = 'Declining'
   OR aw.Re_Engagement_Priority = 'HIGH'
ORDER BY
    CASE aw.Re_Engagement_Priority
        WHEN 'HIGH'   THEN 1
        WHEN 'MEDIUM' THEN 2
        ELSE 3
    END,
    CAST(REPLACE(aw.Score_Change_Pct, '%', '') AS DECIMAL(6,1)) ASC;  -- Biggest drops first


/*
================================================================================
  KPI 17 – COMPETITIVE INTELLIGENCE – ANOMALY & TREND DETECTION
  Module: Competitive Intel
  Logic:  Surface competitor activity signals at territory and district level
          Includes market share change and rep call frequency anomalies
================================================================================
*/
SELECT
    ci.Signal_Id,
    ci.Signal_Type,
    ci.Territory_Durable_Id,
    ci.Territory_Name,
    ci.District_Name,
    ci.Competitor_Name,
    ci.Signal_Description,
    ci.Market_Share_Change_Pct,
    ci.Competitor_Call_Freq_Change,
    ci.Counter_Strategy,
    ci.Detection_Date,
    -- Enrich with live territory hierarchy
    th.Region_Name,
    th.Territory_Code,
    -- Live Zenpep TRx for context (rolling 3M)
    SUM(CAST(r.Normalized_Total_Rx_Quantity AS DECIMAL(10,2))) AS Zenpep_TRx_3M,
    CAST(GETDATE() AS DATE)                                 AS Report_As_Of_Date
FROM hub_insight360.insight360_competitive_intel_dul ci
LEFT JOIN hub_insight360.vw_tdim_terr_hierarchy_zenpep_reporting_dul th
       ON th.Territory_Durable_Id = ci.Territory_Durable_Id
LEFT JOIN hub_insight360.vw_account_territory_zenpep_reporting_dul at2
       ON at2.Territory_Durable_Id = ci.Territory_Durable_Id
      AND at2.sales_force = 'Commercial_Sales_Field_Force'
LEFT JOIN hub_insight360.vw_tfact_prescribersales_zenpep_reporting_dul r
       ON r.HCP_Durable_Id = at2.HCP_Durable_Id
      AND r.Brand_Name = 'ZENPEP'
      AND CAST(r.Month_Ending_Date AS DATE) >= DATEADD(MONTH, -3, CAST(GETDATE() AS DATE))
GROUP BY
    ci.Signal_Id,
    ci.Signal_Type,
    ci.Territory_Durable_Id,
    ci.Territory_Name,
    ci.District_Name,
    ci.Competitor_Name,
    ci.Signal_Description,
    ci.Market_Share_Change_Pct,
    ci.Competitor_Call_Freq_Change,
    ci.Counter_Strategy,
    ci.Detection_Date,
    th.Region_Name,
    th.Territory_Code
ORDER BY
    CAST(ci.Detection_Date AS DATE) DESC,
    -- Largest market share decline first
    CAST(REPLACE(ci.Market_Share_Change_Pct, '%', '') AS DECIMAL(6,1)) ASC;


/*
================================================================================
  KPI 18 – PAYER INTELLIGENCE TRACKING
  Module: Payer Access
  Logic:  Surface current formulary status and recent tier changes
          across commercial plans affecting Zenpep access
================================================================================
*/
SELECT
    pa.Plan_Durable_Id,
    pa.Plan_Name,
    pa.MCO_Organization_Name,
    pa.Channel_Name,
    pa.Formulary_Tier,
    pa.PA_Required,
    pa.Recent_Tier_Change,
    pa.Change_Date,
    pa.Previous_Tier,
    pa.AI_Alert_Flag,
    pa.Affected_HCP_Count,
    pa.Covered_Lives_Est,
    pa.Access_Impact_Level,
    pa.Recommended_Action,
    -- Days since tier change
    CASE WHEN pa.Recent_Tier_Change = 'Yes'
         THEN DATEDIFF(DAY, CAST(pa.Change_Date AS DATE), CAST(GETDATE() AS DATE))
         ELSE NULL
    END                                                     AS Days_Since_Tier_Change,
    -- Tier change direction
    CASE
        WHEN pa.Recent_Tier_Change = 'Yes'
         AND pa.Formulary_Tier > pa.Previous_Tier
            THEN 'WORSENED'
        WHEN pa.Recent_Tier_Change = 'Yes'
         AND pa.Formulary_Tier < pa.Previous_Tier
            THEN 'IMPROVED'
        WHEN pa.Recent_Tier_Change = 'Yes'
            THEN 'CHANGED'
        ELSE 'NO CHANGE'
    END                                                     AS Tier_Change_Direction,
    CAST(GETDATE() AS DATE)                                 AS Report_As_Of_Date
FROM hub_insight360.insight360_payer_access_dul pa
ORDER BY
    CASE pa.Access_Impact_Level
        WHEN 'HIGH'   THEN 1
        WHEN 'MEDIUM' THEN 2
        ELSE 3
    END,
    pa.Covered_Lives_Est DESC;


/*
================================================================================
  KPI 19 – AI-BASED PAYER IMPACT ANALYSIS
  Module: Payer Access
  Logic:  Quantify the Rx impact of payer access changes by estimating
          how many of the affected HCPs' patients are on each plan
================================================================================
*/
WITH payer_impact AS (
    SELECT
        pa.Plan_Durable_Id,
        pa.Plan_Name,
        pa.Channel_Name,
        pa.Formulary_Tier,
        pa.Previous_Tier,
        pa.Recent_Tier_Change,
        pa.AI_Alert_Flag,
        pa.Access_Impact_Level,
        pa.Affected_HCP_Count,
        pa.Covered_Lives_Est,
        pa.Recommended_Action,
        -- Estimated scripts at risk: affected HCPs × avg TRx per HCP on this plan
        -- Using live Rx data for the affected HCP pool
        COALESCE(
            SUM(CAST(r.Normalized_Total_Rx_Quantity AS DECIMAL(10,2))),
            0
        )                                                   AS Affected_HCP_TRx_Rolling_12M
    FROM hub_insight360.insight360_payer_access_dul pa
    -- Join to live Rx fact filtered to this plan
    LEFT JOIN hub_insight360.vw_tfact_prescribersales_zenpep_reporting_dul r
           ON r.Plan_Durable_Id = pa.Plan_Durable_Id
          AND r.Brand_Name = 'ZENPEP'
          AND CAST(r.Month_Ending_Date AS DATE) >= DATEADD(MONTH, -12, CAST(GETDATE() AS DATE))
    GROUP BY
        pa.Plan_Durable_Id,
        pa.Plan_Name,
        pa.Channel_Name,
        pa.Formulary_Tier,
        pa.Previous_Tier,
        pa.Recent_Tier_Change,
        pa.AI_Alert_Flag,
        pa.Access_Impact_Level,
        pa.Affected_HCP_Count,
        pa.Covered_Lives_Est,
        pa.Recommended_Action
)
SELECT
    Plan_Durable_Id,
    Plan_Name,
    Channel_Name,
    Formulary_Tier,
    Previous_Tier,
    Recent_Tier_Change,
    AI_Alert_Flag,
    Access_Impact_Level,
    Affected_HCP_Count,
    Covered_Lives_Est,
    Affected_HCP_TRx_Rolling_12M,
    -- Estimated TRx at risk from tier change (% of volume at risk by tier)
    CAST(
        Affected_HCP_TRx_Rolling_12M *
        CASE Access_Impact_Level
            WHEN 'HIGH'   THEN 0.25   -- 25% of Rx at risk
            WHEN 'MEDIUM' THEN 0.12
            ELSE 0.05
        END
    AS DECIMAL(10,2))                                       AS Estimated_TRx_At_Risk_12M,
    Recommended_Action,
    CAST(GETDATE() AS DATE)                                 AS Report_As_Of_Date
FROM payer_impact
WHERE Recent_Tier_Change = 'Yes'
   OR AI_Alert_Flag = 'Yes'
ORDER BY
    CASE Access_Impact_Level WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
    Estimated_TRx_At_Risk_12M DESC;
