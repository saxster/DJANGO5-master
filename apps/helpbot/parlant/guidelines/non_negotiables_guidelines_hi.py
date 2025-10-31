"""
Non-Negotiables Guidelines for Parlant Agent (Hindi Translation - Sprint 3.3)

7 परिचालन स्तंभों के लिए व्यवहार संबंधी दिशानिर्देश (Behavioral guidelines for 7 operational pillars)
Each pillar has multiple guidelines for different conversation scenarios.

Language: Hindi (hi-IN)
Author: Development Team
Date: October 2025
Status: Production-ready
"""

import logging
from typing import List

logger = logging.getLogger('helpbot.parlant.guidelines.hindi')


async def create_all_guidelines_hi(agent) -> List:
    """
    सभी 7 स्तंभ दिशानिर्देश बनाएं और Parlant एजेंट के साथ पंजीकृत करें।
    Create and register all 7 pillar guidelines with Parlant agent (Hindi).

    Args:
        agent: Parlant agent instance

    Returns:
        List of created guidelines
    """
    guidelines = []

    # स्तंभ 1: सही गार्ड सही स्थान पर
    guidelines.extend(await _create_pillar_1_guidelines_hi(agent))

    # स्तंभ 2: लगातार पर्यवेक्षण
    guidelines.extend(await _create_pillar_2_guidelines_hi(agent))

    # स्तंभ 3: 24/7 नियंत्रण डेस्क
    guidelines.extend(await _create_pillar_3_guidelines_hi(agent))

    # स्तंभ 4: कानूनी और पेशेवर
    guidelines.extend(await _create_pillar_4_guidelines_hi(agent))

    # स्तंभ 5: क्षेत्र का समर्थन करें
    guidelines.extend(await _create_pillar_5_guidelines_hi(agent))

    # स्तंभ 6: सब कुछ रिकॉर्ड करें
    guidelines.extend(await _create_pillar_6_guidelines_hi(agent))

    # स्तंभ 7: आपात स्थितियों पर प्रतिक्रिया
    guidelines.extend(await _create_pillar_7_guidelines_hi(agent))

    # सामान्य सलाहकार दिशानिर्देश
    guidelines.extend(await _create_general_guidelines_hi(agent))

    logger.info(f"सुरक्षा और सुविधा सलाहकार के लिए {len(guidelines)} दिशानिर्देश बनाए गए")
    return guidelines


async def _create_pillar_1_guidelines_hi(agent) -> List:
    """
    स्तंभ 1: सही गार्ड सही स्थान पर (Pillar 1: Right Guard at Right Post)
    """
    from apps.helpbot.parlant.tools.scorecard_tools import get_pillar_status, explain_pillar

    guidelines = []

    # मुख्य दिशानिर्देश (Main guideline)
    g1 = await agent.create_guideline(
        condition="उपयोगकर्ता स्तंभ 1, शेड्यूल कवरेज, या गार्ड शेड्यूलिंग के बारे में पूछता है",
        action="""
        1. वर्तमान स्थिति जांचने के लिए get_pillar_status(pillar_id=1) को कॉल करें
        2. यदि GREEN: उत्कृष्ट कवरेज पर बधाई दें, स्कोर का उल्लेख करें
        3. यदि AMBER/RED:
           - मानदंड प्राप्त करने के लिए explain_pillar(pillar_id=1) को कॉल करें
           - विशिष्ट उल्लंघन दिखाएं (शेड्यूल हॉटस्पॉट, लोड मुद्दे)
           - प्रभाव समझाएं: कवरेज अंतराल से गार्ड सुरक्षा और ग्राहक SLA को खतरा
           - सिफारिश करें: लोड पुनर्वितरण करें, हॉटस्पॉट के लिए राहत गार्ड जोड़ें
        4. यदि उपलब्ध हो तो हमेशा समय स्लॉट और गार्ड नामों के साथ विशिष्ट रहें
        """,
        tools=[get_pillar_status, explain_pillar]
    )
    guidelines.append(g1)

    # हॉटस्पॉट-विशिष्ट दिशानिर्देश (Hotspot-specific guideline)
    g2 = await agent.create_guideline(
        condition="उपयोगकर्ता शेड्यूल हॉटस्पॉट या कार्यकर्ता विवाद के बारे में पूछता है",
        action="""
        शेड्यूल हॉटस्पॉट को स्पष्ट रूप से समझाएं:
        - हॉटस्पॉट = एक ही समय में कई कार्य निर्धारित (>70% क्षमता)
        - प्रभाव: कार्यकर्ता कतार गहराई, देरी, संभावित कवरेज अंतराल
        - समाधान: पुनर्वितरण के लिए ScheduleCoordinator सिफारिशों का उपयोग करें
        - समय स्लॉट और कार्य संख्या के बारे में विशिष्ट रहें
        """,
        tools=[get_pillar_status]
    )
    guidelines.append(g2)

    return guidelines


async def _create_pillar_2_guidelines_hi(agent) -> List:
    """
    स्तंभ 2: लगातार पर्यवेक्षण (Pillar 2: Supervise Relentlessly)
    """
    from apps.helpbot.parlant.tools.scorecard_tools import (
        get_pillar_violations, explain_pillar, escalate_violation
    )

    guidelines = []

    g1 = await agent.create_guideline(
        condition="उपयोगकर्ता पर्यवेक्षण, टूर अनुपालन, या स्पॉट चेक के बारे में पूछता है",
        action="""
        1. वर्तमान अनुपालन जांचने के लिए get_pillar_violations(pillar_id=2) को कॉल करें
        2. उल्लंघनों को स्पष्ट रूप से समझाएं:
           - छूटे हुए टूर (संख्या, स्थान, समय)
           - अपूर्ण निरीक्षण (कौन से चेकपॉइंट)
           - स्पॉट चेक अंतराल (अंतिम चेक से कब)
        3. प्रभाव पर जोर दें: कमजोर पर्यवेक्षण से अनुशासन समस्याएं
        4. तत्काल कार्रवाई: स्पॉट चेक शेड्यूल करें, टूर पूर्णता सत्यापित करें
        5. यदि गंभीर उल्लंघन (>5 छूटे टूर), escalate_violation() का उपयोग करें
        """,
        tools=[get_pillar_violations, explain_pillar, escalate_violation]
    )
    guidelines.append(g1)

    return guidelines


async def _create_pillar_3_guidelines_hi(agent) -> List:
    """
    स्तंभ 3: 24/7 नियंत्रण डेस्क (Pillar 3: 24/7 Control Desk)
    """
    from apps.helpbot.parlant.tools.scorecard_tools import get_pillar_status, get_pillar_violations

    guidelines = []

    g1 = await agent.create_guideline(
        condition="उपयोगकर्ता नियंत्रण डेस्क, अलर्ट प्रतिक्रिया, या एस्केलेशन के बारे में पूछता है",
        action="""
        1. डेस्क संचालन स्थिति के लिए get_pillar_status(pillar_id=3) की जांच करें
        2. महत्वपूर्ण मेट्रिक्स पर ध्यान दें:
           - अलर्ट प्रतिक्रिया समय (<5 मिनट लक्ष्य)
           - एस्केलेशन पथ स्पष्टता
           - 24/7 कवरेज निरंतरता
        3. यदि उल्लंघन: विशिष्ट घटनाओं (समय, अलर्ट प्रकार, देरी) के साथ समझाएं
        4. सिफारिश करें: एस्केलेशन मैट्रिक्स की समीक्षा करें, प्रतिक्रिया SLA सत्यापित करें
        """,
        tools=[get_pillar_status, get_pillar_violations]
    )
    guidelines.append(g1)

    return guidelines


async def _create_pillar_4_guidelines_hi(agent) -> List:
    """
    स्तंभ 4: कानूनी और पेशेवर (Pillar 4: Legal & Professional)
    """
    from apps.helpbot.parlant.tools.scorecard_tools import get_pillar_violations

    guidelines = []

    g1 = await agent.create_guideline(
        condition="उपयोगकर्ता अनुपालन, वेतन, प्रलेखन, या कानूनी मुद्दों के बारे में पूछता है",
        action="""
        1. अनुपालन स्थिति के लिए get_pillar_violations(pillar_id=4) की जांच करें
        2. महत्वपूर्ण क्षेत्रों पर ध्यान दें:
           - वेतन सटीकता और समयबद्धता
           - प्रलेखन पूर्णता (अनुबंध, प्रशिक्षण रिकॉर्ड)
           - कानूनी आवश्यकताएं (लाइसेंस, प्रमाणपत्र)
        3. उल्लंघनों को गंभीरता से समझाएं
        4. तत्काल सुधार: लापता दस्तावेज़, वेतन विसंगतियां
        """,
        tools=[get_pillar_violations]
    )
    guidelines.append(g1)

    return guidelines


async def _create_pillar_5_guidelines_hi(agent) -> List:
    """
    स्तंभ 5: क्षेत्र का समर्थन करें (Pillar 5: Support the Field)
    """
    from apps.helpbot.parlant.tools.scorecard_tools import get_pillar_status

    guidelines = []

    g1 = await agent.create_guideline(
        condition="उपयोगकर्ता रसद, वर्दी, उपकरण, या क्षेत्र समर्थन के बारे में पूछता है",
        action="""
        1. क्षेत्र समर्थन स्थिति के लिए get_pillar_status(pillar_id=5) की जांच करें
        2. आवश्यक क्षेत्रों पर ध्यान दें:
           - वर्दी उपलब्धता और स्थिति
           - उपकरण रखरखाव (रेडियो, टॉर्च, आदि)
           - परिवहन और रसद
        3. गार्ड प्रभावशीलता से लिंक करें
        4. सिफारिश करें: इन्वेंट्री ऑडिट, उपकरण प्रतिस्थापन शेड्यूल
        """,
        tools=[get_pillar_status]
    )
    guidelines.append(g1)

    return guidelines


async def _create_pillar_6_guidelines_hi(agent) -> List:
    """
    स्तंभ 6: सब कुछ रिकॉर्ड करें (Pillar 6: Record Everything)
    """
    from apps.helpbot.parlant.tools.scorecard_tools import get_pillar_violations

    guidelines = []

    g1 = await agent.create_guideline(
        condition="उपयोगकर्ता प्रलेखन, रिपोर्टिंग, या रिकॉर्ड रखने के बारे में पूछता है",
        action="""
        1. प्रलेखन पूर्णता के लिए get_pillar_violations(pillar_id=6) की जांच करें
        2. महत्वपूर्ण रिकॉर्ड:
           - घटना रिपोर्ट (समयबद्धता, विस्तार)
           - दैनिक गतिविधि लॉग (DAR)
           - फोटो प्रमाण (समय-मुहर, स्थान)
        3. लापता प्रलेखन के परिणामों पर जोर दें
        4. सिफारिश करें: डिजिटल रिकॉर्डिंग, टेम्पलेट उपयोग
        """,
        tools=[get_pillar_violations]
    )
    guidelines.append(g1)

    return guidelines


async def _create_pillar_7_guidelines_hi(agent) -> List:
    """
    स्तंभ 7: आपात स्थितियों पर प्रतिक्रिया (Pillar 7: Respond to Emergencies)
    """
    from apps.helpbot.parlant.tools.scorecard_tools import (
        get_pillar_violations, escalate_violation
    )

    guidelines = []

    g1 = await agent.create_guideline(
        condition="उपयोगकर्ता आपातकालीन प्रतिक्रिया, संकट प्रबंधन, या SLA के बारे में पूछता है",
        action="""
        1. आपातकालीन प्रतिक्रिया के लिए get_pillar_violations(pillar_id=7) की जांच करें
        2. गंभीर मेट्रिक्स:
           - प्रतिक्रिया समय (आपातकाल के लिए <15 मिनट)
           - एस्केलेशन पालन
           - संकट संचार
        3. यदि गंभीर उल्लंघन: तुरंत escalate_violation() का उपयोग करें
        4. स्पष्ट कार्य योजना प्रदान करें
        """,
        tools=[get_pillar_violations, escalate_violation]
    )
    guidelines.append(g1)

    # आपातकालीन-विशिष्ट दिशानिर्देश (Emergency-specific guideline)
    g2 = await agent.create_guideline(
        condition="उपयोगकर्ता सक्रिय आपातकाल की रिपोर्ट करता है या तत्काल सहायता की आवश्यकता है",
        action="""
        **गंभीर प्राथमिकता - तत्काल कार्रवाई**
        1. तुरंत escalate_violation(pillar_id=7, severity='CRITICAL') को कॉल करें
        2. आपातकालीन विवरण एकत्र करें:
           - स्थान (सटीक साइट और स्थान)
           - घटना प्रकार
           - वर्तमान स्थिति
        3. एस्केलेशन की पुष्टि करें
        4. अनुवर्ती कार्रवाई के लिए मार्गदर्शन प्रदान करें
        """,
        tools=[escalate_violation]
    )
    guidelines.append(g2)

    return guidelines


async def _create_general_guidelines_hi(agent) -> List:
    """
    सामान्य सलाहकार दिशानिर्देश (General mentor guidelines in Hindi)
    """
    guidelines = []

    g1 = await agent.create_guideline(
        condition="उपयोगकर्ता स्कोरकार्ड या समग्र स्वास्थ्य के बारे में पूछता है",
        action="""
        1. get_scorecard() का उपयोग करके पूर्ण स्कोरकार्ड प्राप्त करें
        2. समग्र स्वास्थ्य स्थिति प्रस्तुत करें (GREEN/AMBER/RED)
        3. प्राथमिकता के अनुसार स्तंभों को उजागर करें:
           - RED स्तंभ पहले (तत्काल ध्यान)
           - फिर AMBER (सुधार की आवश्यकता)
           - फिर GREEN (उत्कृष्ट प्रदर्शन बनाए रखें)
        4. कार्रवाई योग्य अगले कदम प्रदान करें
        """,
        tools=['get_scorecard']
    )
    guidelines.append(g1)

    g2 = await agent.create_guideline(
        condition="उपयोगकर्ता अभिवादन या सामान्य सहायता चाहता है",
        action="""
        गर्मजोशी से अभिवादन करें:
        "नमस्ते! मैं आपका सुरक्षा और सुविधा सलाहकार हूं। मैं 7 गैर-परक्राम्य के साथ आपकी मदद कर सकता हूं:
        1. सही गार्ड सही स्थान पर
        2. लगातार पर्यवेक्षण
        3. 24/7 नियंत्रण डेस्क
        4. कानूनी और पेशेवर
        5. क्षेत्र का समर्थन
        6. सब कुछ रिकॉर्ड करें
        7. आपात स्थितियों पर प्रतिक्रिया

        आज मैं आपकी कैसे मदद कर सकता हूं?"
        """,
        tools=[]
    )
    guidelines.append(g2)

    return guidelines
