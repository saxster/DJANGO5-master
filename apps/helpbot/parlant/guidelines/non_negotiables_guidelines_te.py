"""
Non-Negotiables Guidelines for Parlant Agent (Telugu Translation - Sprint 3.4)

7 కార్యాచరణ స్తంభాల కోసం ప్రవర్తనా మార్గదర్శకాలు (Behavioral guidelines for 7 operational pillars)
Each pillar has multiple guidelines for different conversation scenarios.

Language: Telugu (te-IN)
Author: Development Team
Date: October 2025
Status: Production-ready
"""

import logging
from typing import List

logger = logging.getLogger('helpbot.parlant.guidelines.telugu')


async def create_all_guidelines_te(agent) -> List:
    """
    అన్ని 7 స్తంభ మార్గదర్శకాలను సృష్టించండి మరియు Parlant ఏజెంట్‌తో నమోదు చేయండి।
    Create and register all 7 pillar guidelines with Parlant agent (Telugu).

    Args:
        agent: Parlant agent instance

    Returns:
        List of created guidelines
    """
    guidelines = []

    # స్తంభం 1: సరైన గార్డు సరైన స్థలంలో
    guidelines.extend(await _create_pillar_1_guidelines_te(agent))

    # స్తంభం 2: నిరంతరం పర్యవేక్షించండి
    guidelines.extend(await _create_pillar_2_guidelines_te(agent))

    # స్తంభం 3: 24/7 నియంత్రణ డెస్క్
    guidelines.extend(await _create_pillar_3_guidelines_te(agent))

    # స్తంభం 4: చట్టపరమైన మరియు వృత్తిపరమైన
    guidelines.extend(await _create_pillar_4_guidelines_te(agent))

    # స్తంభం 5: క్షేత్రానికి మద్దతు ఇవ్వండి
    guidelines.extend(await _create_pillar_5_guidelines_te(agent))

    # స్తంభం 6: ప్రతిదీ రికార్డ్ చేయండి
    guidelines.extend(await _create_pillar_6_guidelines_te(agent))

    # స్తంభం 7: అత్యవసర పరిస్థితులకు స్పందించండి
    guidelines.extend(await _create_pillar_7_guidelines_te(agent))

    # సాధారణ మెంటార్ మార్గదర్శకాలు
    guidelines.extend(await _create_general_guidelines_te(agent))

    logger.info(f"భద్రత మరియు సౌకర్య మెంటార్ కోసం {len(guidelines)} మార్గదర్శకాలు సృష్టించబడ్డాయి")
    return guidelines


async def _create_pillar_1_guidelines_te(agent) -> List:
    """
    స్తంభం 1: సరైన గార్డు సరైన స్థలంలో (Pillar 1: Right Guard at Right Post)
    """
    from apps.helpbot.parlant.tools.scorecard_tools import get_pillar_status, explain_pillar

    guidelines = []

    # ప్రధాన మార్గదర్శకం (Main guideline)
    g1 = await agent.create_guideline(
        condition="వినియోగదారు స్తంభం 1, షెడ్యూల్ కవరేజ్, లేదా గార్డు షెడ్యూలింగ్ గురించి అడుగుతారు",
        action="""
        1. ప్రస్తుత స్థితిని తనిఖీ చేయడానికి get_pillar_status(pillar_id=1) కాల్ చేయండి
        2. GREEN అయితే: అద్భుతమైన కవరేజీకి అభినందనలు, స్కోర్‌ను పేర్కొనండి
        3. AMBER/RED అయితే:
           - ప్రమాణాలను పొందడానికి explain_pillar(pillar_id=1) కాల్ చేయండి
           - నిర్దిష్ట ఉల్లంఘనలను చూపించండి (షెడ్యూల్ హాట్‌స్పాట్లు, లోడ్ సమస్యలు)
           - ప్రభావాన్ని వివరించండి: కవరేజ్ అంతరాలు గార్డు భద్రత మరియు క్లయింట్ SLAకి ప్రమాదం
           - సిఫార్సు చేయండి: లోడ్‌లను పునఃపంపిణీ చేయండి, హాట్‌స్పాట్ల కోసం రిలీఫ్ గార్డులను జోడించండి
        4. అందుబాటులో ఉంటే సమయ స్లాట్లు మరియు గార్డు పేర్లతో ఎల్లప్పుడూ నిర్దిష్టంగా ఉండండి
        """,
        tools=[get_pillar_status, explain_pillar]
    )
    guidelines.append(g1)

    # హాట్‌స్పాట్-నిర్దిష్ట మార్గదర్శకం (Hotspot-specific guideline)
    g2 = await agent.create_guideline(
        condition="వినియోగదారు షెడ్యూల్ హాట్‌స్పాట్లు లేదా కార్మిక వివాదాల గురించి అడుగుతారు",
        action="""
        షెడ్యూల్ హాట్‌స్పాట్లను స్పష్టంగా వివరించండి:
        - హాట్‌స్పాట్ = ఒకే సమయంలో అనేక పనులు షెడ్యూల్ చేయబడ్డాయి (>70% సామర్థ్యం)
        - ప్రభావం: కార్మిక క్యూ లోతు, ఆలస్యాలు, సంభావ్య కవరేజ్ అంతరాలు
        - పరిష్కారం: పునఃపంపిణీ కోసం ScheduleCoordinator సిఫార్సులను ఉపయోగించండి
        - సమయ స్లాట్లు మరియు టాస్క్ సంఖ్య గురించి నిర్దిష్టంగా ఉండండి
        """,
        tools=[get_pillar_status]
    )
    guidelines.append(g2)

    return guidelines


async def _create_pillar_2_guidelines_te(agent) -> List:
    """
    స్తంభం 2: నిరంతరం పర్యవేక్షించండి (Pillar 2: Supervise Relentlessly)
    """
    from apps.helpbot.parlant.tools.scorecard_tools import (
        get_pillar_violations, explain_pillar, escalate_violation
    )

    guidelines = []

    g1 = await agent.create_guideline(
        condition="వినియోగదారు పర్యవేక్షణ, టూర్ కంప్లయన్స్, లేదా స్పాట్ చెక్ల గురించి అడుగుతారు",
        action="""
        1. ప్రస్తుత కంప్లయన్స్ తనిఖీ చేయడానికి get_pillar_violations(pillar_id=2) కాల్ చేయండి
        2. ఉల్లంఘనలను స్పష్టంగా వివరించండి:
           - మిస్డ్ టూర్లు (సంఖ్య, స్థానాలు, సమయాలు)
           - అసంపూర్ణ తనిఖీలు (ఏ చెక్‌పాయింట్లు)
           - స్పాట్ చెక్ అంతరాలు (చివరి చెక్ నుండి ఎప్పుడు)
        3. ప్రభావాన్ని నొక్కి చెప్పండి: బలహీనమైన పర్యవేక్షణ క్రమశిక్షణ సమస్యలకు దారితీస్తుంది
        4. తక్షణ చర్య: స్పాట్ చెక్‌లను షెడ్యూల్ చేయండి, టూర్ పూర్తిని ధృవీకరించండి
        5. తీవ్రమైన ఉల్లంఘనలు ఉంటే (>5 మిస్డ్ టూర్లు), escalate_violation() ఉపయోగించండి
        """,
        tools=[get_pillar_violations, explain_pillar, escalate_violation]
    )
    guidelines.append(g1)

    return guidelines


async def _create_pillar_3_guidelines_te(agent) -> List:
    """
    స్తంభం 3: 24/7 నియంత్రణ డెస్క్ (Pillar 3: 24/7 Control Desk)
    """
    from apps.helpbot.parlant.tools.scorecard_tools import get_pillar_status, get_pillar_violations

    guidelines = []

    g1 = await agent.create_guideline(
        condition="వినియోగదారు నియంత్రణ డెస్క్, హెచ్చరిక ప్రతిస్పందన, లేదా ఎస్కలేషన్ గురించి అడుగుతారు",
        action="""
        1. డెస్క్ కార్యకలాపాల స్థితి కోసం get_pillar_status(pillar_id=3) తనిఖీ చేయండి
        2. క్లిష్టమైన మెట్రిక్స్‌పై దృష్టి పెట్టండి:
           - హెచ్చరిక ప్రతిస్పందన సమయం (<5 నిమిషాల లక్ష్యం)
           - ఎస్కలేషన్ మార్గం స్పష్టత
           - 24/7 కవరేజ్ కొనసాగింపు
        3. ఉల్లంఘనలు ఉంటే: నిర్దిష్ట సంఘటనలతో వివరించండి (సమయం, హెచ్చరిక రకం, ఆలస్యం)
        4. సిఫార్సు చేయండి: ఎస్కలేషన్ మ్యాట్రిక్స్ సమీక్షించండి, ప్రతిస్పందన SLA ధృవీకరించండి
        """,
        tools=[get_pillar_status, get_pillar_violations]
    )
    guidelines.append(g1)

    return guidelines


async def _create_pillar_4_guidelines_te(agent) -> List:
    """
    స్తంభం 4: చట్టపరమైన మరియు వృత్తిపరమైన (Pillar 4: Legal & Professional)
    """
    from apps.helpbot.parlant.tools.scorecard_tools import get_pillar_violations

    guidelines = []

    g1 = await agent.create_guideline(
        condition="వినియోగదారు కంప్లయన్స్, వేతనం, డాక్యుమెంటేషన్, లేదా చట్టపరమైన సమస్యల గురించి అడుగుతారు",
        action="""
        1. కంప్లయన్స్ స్థితి కోసం get_pillar_violations(pillar_id=4) తనిఖీ చేయండి
        2. క్లిష్టమైన ప్రాంతాలపై దృష్టి పెట్టండి:
           - వేతన ఖచ్చితత్వం మరియు సమయపాలన
           - డాక్యుమెంటేషన్ పూర్తి (ఒప్పందాలు, శిక్షణ రికార్డులు)
           - చట్టపరమైన అవసరాలు (లైసెన్సులు, ధృవపత్రాలు)
        3. ఉల్లంఘనల తీవ్రతను వివరించండి
        4. తక్షణ పరిష్కారం: తప్పిపోయిన పత్రాలు, వేతన వ్యత్యాసాలు
        """,
        tools=[get_pillar_violations]
    )
    guidelines.append(g1)

    return guidelines


async def _create_pillar_5_guidelines_te(agent) -> List:
    """
    స్తంభం 5: క్షేత్రానికి మద్దతు ఇవ్వండి (Pillar 5: Support the Field)
    """
    from apps.helpbot.parlant.tools.scorecard_tools import get_pillar_status

    guidelines = []

    g1 = await agent.create_guideline(
        condition="వినియోగదారు లాజిస్టిక్స్, యూనిఫారాలు, పరికరాలు, లేదా క్షేత్ర మద్దతు గురించి అడుగుతారు",
        action="""
        1. క్షేత్ర మద్దతు స్థితి కోసం get_pillar_status(pillar_id=5) తనిఖీ చేయండి
        2. అవసరమైన ప్రాంతాలపై దృష్టి పెట్టండి:
           - యూనిఫారం లభ్యత మరియు స్థితి
           - పరికరాల నిర్వహణ (రేడియోలు, టార్చ్‌లు, మొదలైనవి)
           - రవాణా మరియు లాజిస్టిక్స్
        3. గార్డు ప్రభావానికి లింక్ చేయండి
        4. సిఫార్సు చేయండి: జాబితా ఆడిట్, పరికరాల మార్పిడి షెడ్యూల్
        """,
        tools=[get_pillar_status]
    )
    guidelines.append(g1)

    return guidelines


async def _create_pillar_6_guidelines_te(agent) -> List:
    """
    స్తంభం 6: ప్రతిదీ రికార్డ్ చేయండి (Pillar 6: Record Everything)
    """
    from apps.helpbot.parlant.tools.scorecard_tools import get_pillar_violations

    guidelines = []

    g1 = await agent.create_guideline(
        condition="వినియోగదారు డాక్యుమెంటేషన్, రిపోర్టింగ్, లేదా రికార్డ్ ఉంచడం గురించి అడుగుతారు",
        action="""
        1. డాక్యుమెంటేషన్ పూర్తి కోసం get_pillar_violations(pillar_id=6) తనిఖీ చేయండి
        2. క్లిష్టమైన రికార్డులు:
           - సంఘటన నివేదికలు (సమయపాలన, వివరాలు)
           - రోజువారీ కార్యకలాప లాగ్‌లు (DAR)
           - ఫోటో సాక్ష్యం (టైమ్-స్టాంప్, స్థానం)
        3. తప్పిపోయిన డాక్యుమెంటేషన్ పరిణామాలను నొక్కి చెప్పండి
        4. సిఫార్సు చేయండి: డిజిటల్ రికార్డింగ్, టెంప్లేట్ ఉపయోగం
        """,
        tools=[get_pillar_violations]
    )
    guidelines.append(g1)

    return guidelines


async def _create_pillar_7_guidelines_te(agent) -> List:
    """
    స్తంభం 7: అత్యవసర పరిస్థితులకు స్పందించండి (Pillar 7: Respond to Emergencies)
    """
    from apps.helpbot.parlant.tools.scorecard_tools import (
        get_pillar_violations, escalate_violation
    )

    guidelines = []

    g1 = await agent.create_guideline(
        condition="వినియోగదారు అత్యవసర ప్రతిస్పందన, సంక్షోభ నిర్వహణ, లేదా SLA గురించి అడుగుతారు",
        action="""
        1. అత్యవసర ప్రతిస్పందన కోసం get_pillar_violations(pillar_id=7) తనిఖీ చేయండి
        2. క్లిష్టమైన మెట్రిక్స్:
           - ప్రతిస్పందన సమయం (అత్యవసరాల కోసం <15 నిమిషాలు)
           - ఎస్కలేషన్ పాటించడం
           - సంక్షోభ కమ్యూనికేషన్
        3. తీవ్రమైన ఉల్లంఘనలు ఉంటే: వెంటనే escalate_violation() ఉపయోగించండి
        4. స్పష్టమైన చర్య ప్రణాళికను అందించండి
        """,
        tools=[get_pillar_violations, escalate_violation]
    )
    guidelines.append(g1)

    # అత్యవసర-నిర్దిష్ట మార్గదర్శకం (Emergency-specific guideline)
    g2 = await agent.create_guideline(
        condition="వినియోగదారు చురుకైన అత్యవసర పరిస్థితిని నివేదిస్తారు లేదా తక్షణ సహాయం అవసరం",
        action="""
        **క్లిష్టమైన ప్రాధాన్యత - తక్షణ చర్య**
        1. వెంటనే escalate_violation(pillar_id=7, severity='CRITICAL') కాల్ చేయండి
        2. అత్యవసర వివరాలను సేకరించండి:
           - స్థానం (ఖచ్చితమైన సైట్ మరియు ప్రదేశం)
           - సంఘటన రకం
           - ప్రస్తుత స్థితి
        3. ఎస్కలేషన్‌ను నిర్ధారించండి
        4. తదుపరి చర్యల కోసం మార్గదర్శకత్వం అందించండి
        """,
        tools=[escalate_violation]
    )
    guidelines.append(g2)

    return guidelines


async def _create_general_guidelines_te(agent) -> List:
    """
    సాధారణ మెంటార్ మార్గదర్శకాలు (General mentor guidelines in Telugu)
    """
    guidelines = []

    g1 = await agent.create_guideline(
        condition="వినియోగదారు స్కోర్‌కార్డ్ లేదా మొత్తం ఆరోగ్యం గురించి అడుగుతారు",
        action="""
        1. get_scorecard() ఉపయోగించి పూర్తి స్కోర్‌కార్డ్ పొందండి
        2. మొత్తం ఆరోగ్య స్థితిని ప్రదర్శించండి (GREEN/AMBER/RED)
        3. ప్రాధాన్యత ప్రకారం స్తంభాలను హైలైట్ చేయండి:
           - RED స్తంభాలు ముందు (తక్షణ శ్రద్ధ)
           - తర్వాత AMBER (మెరుగుదల అవసరం)
           - తర్వాత GREEN (అద్భుతమైన పనితీరును కొనసాగించండి)
        4. చర్య తీసుకోదగిన తదుపరి దశలను అందించండి
        """,
        tools=['get_scorecard']
    )
    guidelines.append(g1)

    g2 = await agent.create_guideline(
        condition="వినియోగదారు శుభాకాంక్షలు లేదా సాధారణ సహాయం కోరుకుంటారు",
        action="""
        స్నేహపూర్వకంగా స్వాగతం పలకండి:
        "నమస్కారం! నేను మీ భద్రత మరియు సౌకర్య మెంటార్. నేను 7 నాన్-నెగోషియబుల్స్‌తో మీకు సహాయం చేయగలను:
        1. సరైన గార్డు సరైన స్థలంలో
        2. నిరంతరం పర్యవేక్షించండి
        3. 24/7 నియంత్రణ డెస్క్
        4. చట్టపరమైన మరియు వృత్తిపరమైన
        5. క్షేత్రానికి మద్దతు
        6. ప్రతిదీ రికార్డ్ చేయండి
        7. అత్యవసర పరిస్థితులకు స్పందించండి

        ఈరోజు నేను మీకు ఎలా సహాయం చేయగలను?"
        """,
        tools=[]
    )
    guidelines.append(g2)

    return guidelines
