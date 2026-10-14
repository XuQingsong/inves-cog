"""Handwritten K16 cases; original fixture and golden files remain immutable."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import shutil
from lxml import etree
from inves_cog.ingest.fundamentals.segments import parse_segments

def assert_k16_cases(root):
    source=Path(__file__).resolve().parents[1]/'fixtures/phase1/m2/xbrl'
    ns={'x':'http://www.xbrl.org/2003/instance','d':'http://xbrl.org/2006/xbrldi'}
    def build(name):
        folder=root/name;folder.mkdir(parents=True)
        for fixture in source.iterdir():shutil.copyfile(fixture,folder/fixture.name)
        schema=folder/'company.xsd'
        extra=''.join(f'<xs:element name="{member}" type="xs:string"/>' for member in ['AggregateMember','SegmentDomain','ProfitOnlyMember'])
        schema.write_text(schema.read_text().replace('</xs:schema>',extra+'</xs:schema>'))
        return folder,etree.fromstring((folder/'instance.xml').read_bytes())
    def member_context(document,identity,member,axis='us-gaap:StatementBusinessSegmentsAxis'):
        template=document.find("x:context[@id='client']",ns)
        context=deepcopy(template);context.set('id',identity)
        dimension=context.find('.//d:explicitMember',ns);dimension.set('dimension',axis);dimension.text=member
        document.append(context)
    def fact(document,identity,name,value):
        element=etree.SubElement(document,'{http://example.invalid/us-gaap}'+name,contextRef=identity,unitRef='usd',decimals='0')
        if value is None:element.set('{http://www.w3.org/2001/XMLSchema-instance}nil','true')
        else:element.text=str(value)
    def parsed(folder,document,**kwargs):
        (folder/'instance.xml').write_bytes(etree.tostring(document))
        return parse_segments(folder/'instance.xml',ticker='AMD',accession='k16-handwritten',filed=date(2026,8,1),**kwargs)
    # A profit-only reconciliation is kept with NULL revenue and excluded from
    # the revenue sum; a reported nil revenue remains an unknown amount.
    folder,document=build('profit-only')
    gaap=folder/'us-gaap.xsd';gaap.write_text(gaap.read_text().replace('</xs:schema>','<xs:element name="CorporateNonSegmentMember" type="xs:string"/></xs:schema>'))
    member_context(document,'corporate','us-gaap:CorporateNonSegmentMember','us-gaap:ConsolidationItemsAxis')
    fact(document,'corporate','OperatingIncomeLoss',3)
    rows=parsed(folder,document)
    corporate=next(row for row in rows if row['segment_raw']=='CorporateNonSegmentMember')
    assert corporate['revenue'] is None and corporate['segment_profit']==3
    assert corporate['evidence']['sum_included'] is False
    assert all('segment_sum_mismatch' not in row['health_codes'] for row in rows)
    fact(document,'corporate','RevenueFromContractWithCustomerExcludingAssessedTax',None)
    assert any('segment_sum_mismatch' in row['health_codes'] for row in parsed(folder,document))
    # Definition relationships prove the subtotal; no name or value matching.
    folder,document=build('subtotal')
    member_context(document,'aggregate','fixture:AggregateMember')
    fact(document,'aggregate','RevenueFromContractWithCustomerExcludingAssessedTax',102)
    role='http://example.invalid/role/segment-revenue'
    links=f'''<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink"><link:definitionLink xlink:type="extended" xlink:role="{role}">
      <link:loc xlink:type="locator" xlink:href="us-gaap.xsd#axis" xlink:label="axis"/>
      <link:loc xlink:type="locator" xlink:href="company.xsd#domain" xlink:label="domain"/>
      <link:loc xlink:type="locator" xlink:href="company.xsd#aggregate" xlink:label="aggregate"/>
      <link:loc xlink:type="locator" xlink:href="company.xsd#client" xlink:label="client"/>
      <link:loc xlink:type="locator" xlink:href="company.xsd#datacenter" xlink:label="datacenter"/>
      <link:definitionArc xlink:type="arc" xlink:arcrole="http://xbrl.org/int/dim/arcrole/dimension-domain" xlink:from="axis" xlink:to="domain"/>
      <link:definitionArc xlink:type="arc" xlink:arcrole="http://xbrl.org/int/dim/arcrole/domain-member" xlink:from="domain" xlink:to="aggregate"/>
      <link:definitionArc xlink:type="arc" xlink:arcrole="http://xbrl.org/int/dim/arcrole/domain-member" xlink:from="aggregate" xlink:to="client"/>
      <link:definitionArc xlink:type="arc" xlink:arcrole="http://xbrl.org/int/dim/arcrole/domain-member" xlink:from="aggregate" xlink:to="datacenter"/>
    </link:definitionLink></link:linkbase>'''
    (folder/'definition.xml').write_text(links)
    for name,ids in [('us-gaap.xsd',{'StatementBusinessSegmentsAxis':'axis'}),('company.xsd',{'SegmentDomain':'domain','AggregateMember':'aggregate','ClientMember':'client','DataCenterMember':'datacenter'})]:
        schema=folder/name;text=schema.read_text()
        for member,identity in ids.items():text=text.replace(f'name="{member}"',f'id="{identity}" name="{member}"')
        if name=='company.xsd':
            text=text.replace('</xs:schema>','<xs:annotation><xs:appinfo><link:linkbaseRef xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink" xlink:type="simple" xlink:href="definition.xml"/></xs:appinfo></xs:annotation></xs:schema>')
        schema.write_text(text)
    rows=parsed(folder,document)
    assert {row['segment_raw'] for row in rows if row['axis']=='business'}=={'ClientMember','DataCenterMember'}
    subtotal=next(row for row in rows if row['segment_raw']=='AggregateMember')
    assert subtotal['axis']=='summary' and subtotal['revenue']==102
    assert subtotal['evidence']['sum_included'] is False
    assert all('segment_sum_mismatch' not in row['health_codes'] for row in rows)
    # Weighted rendering is explicit original evidence, never inferred by
    # trying combinations until the consolidated number happens to match.
    folder,document=build('weight')
    for element in document:
        if element.get('contextRef')=='eliminations':element.text='2'
    html='<table><tr><td>Elimination</td><td>(<ix:nonFraction xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax" contextRef="eliminations" scale="0">2</ix:nonFraction>)</td></tr></table>'
    rows=parsed(folder,document,primary_html=html)
    elimination=next(row for row in rows if row['axis']=='elimination')
    assert elimination['revenue']==2 and elimination['evidence']['revenue_sum_weight']==-1
    assert all('segment_sum_mismatch' not in row['health_codes'] for row in rows)
