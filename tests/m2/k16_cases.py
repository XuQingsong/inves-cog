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

    # Real SEC originals include an XML encoding declaration. Its presence
    # must not silently disable section/column or displayed-sign evidence.
    encoded='<?xml version="1.0" encoding="UTF-8"?>'+html
    rows=parsed(folder,document,primary_html=encoded)
    assert next(r for r in rows if r['axis']=='elimination')['evidence']['revenue_sum_weight']==-1

    # The same concept can occur in a separate internal-revenue section.
    # Preserve that disclosure without subtracting it from external revenue.
    folder,document=build('separate-section')
    next(e for e in document if e.get('contextRef')=='total').text='102'
    concept='us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'
    def cell(context,value):return f'<td><ix:nonFraction name="{concept}" contextRef="{context}">{value}</ix:nonFraction></td>'
    table='<table><tr><td>Segment revenue:</td></tr><tr><td>Client</td>'+cell('client',52)+'</tr><tr><td>Datacenter</td>'+cell('datacenter',50)+'</tr><tr><td>Total</td>'+cell('total',102)+'</tr><tr><td>Intersegment revenue:</td></tr><tr><td>Elimination</td>'+cell('eliminations',-2)+'</tr></table>'
    rows=parsed(folder,document,primary_html=table)
    adjustment=next(r for r in rows if r['axis']=='elimination')
    assert adjustment['revenue']==-2 and adjustment['evidence']['sum_included'] is False
    assert all('segment_sum_mismatch' not in r['health_codes'] for r in rows)
    # An actual reported nil in the selected section is still unknown.
    next(e for e in document if e.get('contextRef')=='eliminations').set('{http://www.w3.org/2001/XMLSchema-instance}nil','true')
    same_section=table.replace('<tr><td>Intersegment revenue:</td></tr>','')
    assert any('segment_sum_mismatch' in r['health_codes'] for r in parsed(folder,document,primary_html=same_section))

    # Positive internal sales are subtracted only when the original ordered
    # subtotal/intersegment/net rows establish the sign, never to fit numbers.
    folder,document=build('gross-net')
    gaap=folder/'us-gaap.xsd';gaap.write_text(gaap.read_text().replace('</xs:schema>','<xs:element name="OperatingSegmentsMember" type="xs:string"/></xs:schema>'))
    member_context(document,'gross','us-gaap:OperatingSegmentsMember','us-gaap:ConsolidationItemsAxis')
    fact(document,'gross','RevenueFromContractWithCustomerExcludingAssessedTax',102)
    next(e for e in document if e.get('contextRef')=='eliminations').text='2'
    table='<table><tr><td>Sales</td>'+cell('client',52)+cell('datacenter',50)+cell('gross',102)+'</tr><tr><td>Intersegment sales</td><td></td><td></td>'+cell('eliminations',2)+'</tr><tr><td>Net Sales</td><td></td><td></td>'+cell('total',100)+'</tr></table>'
    rows=parsed(folder,document,primary_html=table)
    assert next(r for r in rows if r['segment_raw']=='IntersegmentEliminationMember')['evidence']['revenue_sum_weight']==-1
    assert all('segment_sum_mismatch' not in r['health_codes'] for r in rows)
    spanning=table.replace('<td></td><td></td>','<td></td>').replace(cell('eliminations',2),cell('eliminations',2).replace('<td>','<td colspan="2">',1)).replace(cell('total',100),cell('total',100).replace('<td>','<td colspan="2">',1))
    assert all('segment_sum_mismatch' not in r['health_codes'] for r in parsed(folder,document,primary_html=spanning))
    wrong_order=table.replace('Net Sales','Unrelated amount')
    assert any('segment_sum_mismatch' in r['health_codes'] for r in parsed(folder,document,primary_html=wrong_order))

    # A dimensionless revenue component is admitted by the filing's explicit
    # calculation arc, rather than by subtracting the reported segment sum.
    folder,document=build('calculation-component')
    for e in list(document):
        if e.get('contextRef')=='eliminations':document.remove(e)
        elif e.tag.endswith('RevenueFromContractWithCustomerExcludingAssessedTax'):
            e.tag='{http://example.invalid/us-gaap}Revenues'
            if e.get('contextRef')=='total':e.text='107'
    fact(document,'total','InsuranceServicesRevenue',5)
    gaap=folder/'us-gaap.xsd';text=gaap.read_text().replace('</xs:schema>','<xs:element id="revenues" name="Revenues" type="xbrli:monetaryItemType" substitutionGroup="xbrli:item" xbrli:periodType="duration"/><xs:element id="insurance" name="InsuranceServicesRevenue" type="xbrli:monetaryItemType" substitutionGroup="xbrli:item" xbrli:periodType="duration"/></xs:schema>');gaap.write_text(text)
    role='http://example.invalid/role/operations'
    (folder/'calculation.xml').write_text(f'<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink"><link:calculationLink xlink:type="extended" xlink:role="{role}"><link:loc xlink:type="locator" xlink:href="us-gaap.xsd#revenues" xlink:label="revenues"/><link:loc xlink:type="locator" xlink:href="us-gaap.xsd#insurance" xlink:label="insurance"/><link:calculationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item" xlink:from="revenues" xlink:to="insurance" weight="1"/></link:calculationLink></link:linkbase>')
    schema=folder/'company.xsd';schema.write_text(schema.read_text().replace('</xs:schema>','<xs:annotation><xs:appinfo><link:linkbaseRef xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink" xlink:type="simple" xlink:href="calculation.xml"/></xs:appinfo></xs:annotation></xs:schema>'))
    rows=parsed(folder,document)
    component=next(r for r in rows if r['segment_raw']=='InsuranceServicesRevenue')
    assert component['axis']=='elimination' and component['revenue']==5
    assert component['evidence']['weight_source']['linkrole']==role
    assert all('segment_sum_mismatch' not in r['health_codes'] for r in rows)
    calculation=folder/'calculation.xml';calculation.write_text(calculation.read_text().replace('http://www.xbrl.org/2003/arcrole/summation-item','https://xbrl.org/2023/arcrole/summation-item'))
    assert any(r['segment_raw']=='InsuranceServicesRevenue' for r in parsed(folder,document))
    # Explicit reconciliation already explains the amount; do not count a
    # dimensionless component a second time or hide a reported nil amount.
    fact(document,'eliminations','Revenues',5)
    rows=parsed(folder,document)
    assert not [r for r in rows if r['segment_raw']=='InsuranceServicesRevenue']
    assert all('segment_sum_mismatch' not in r['health_codes'] for r in rows)

    # The approved company member is limited to the actual GEV namespace and
    # ticker. A third dimension does not contaminate its valid sibling.
    folder,document=build('gev')
    for schema in ['company.xsd','us-gaap.xsd']:
        p=folder/schema
        text=p.read_text().replace('http://example.invalid/us-gaap','http://fasb.org/us-gaap/2026').replace('http://example.invalid/company','http://www.gevernova.com/20260630')
        if schema=='company.xsd':
            text=text.replace('</xs:schema>','<xs:element name="OperatingSegmentsExcludingIntersegmentEliminationMember" type="xs:string"/><xs:import namespace="http://fasb.org/srt/2026" schemaLocation="srt.xsd"/></xs:schema>')
        else:text=text.replace('</xs:schema>','<xs:element name="OperatingSegmentsMember" type="xs:string"/><xs:element name="SubsegmentsAxis" type="xs:string"/></xs:schema>')
        p.write_text(text)
    (folder/'srt.xsd').write_text('<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="http://fasb.org/srt/2026"><xs:element name="ConsolidationItemsAxis" type="xs:string"/></xs:schema>')
    xml=etree.tostring(document).decode().replace('http://example.invalid/us-gaap','http://fasb.org/us-gaap/2026').replace('http://example.invalid/company','http://www.gevernova.com/20260630').replace('<xbrli:xbrl ','<xbrli:xbrl xmlns:srt="http://fasb.org/srt/2026" ')
    document=etree.fromstring(xml.encode())
    for identity in ['client','datacenter']:
        context=document.find(f"x:context[@id='{identity}']",ns)
        segment=context.find('x:entity/x:segment',ns)
        auxiliary=etree.SubElement(segment,'{'+ns['d']+'}explicitMember',dimension='srt:ConsolidationItemsAxis')
        auxiliary.text='fixture:OperatingSegmentsExcludingIntersegmentEliminationMember'
    (folder/'instance.xml').write_bytes(etree.tostring(document))
    def gev_rows(ticker='GEV'):
        return parse_segments(folder/'instance.xml',ticker=ticker,accession='gev-handwritten',filed=date(2026,8,1))
    assert {r['segment_raw'] for r in gev_rows() if r['axis']=='business'}=={'ClientMember','DataCenterMember'}
    assert not [r for r in gev_rows('AMD') if r['axis']=='business']
    changed=etree.fromstring(etree.tostring(document))
    client=changed.find("x:context[@id='client']/x:entity/x:segment",ns)
    third=etree.SubElement(client,'{'+ns['d']+'}explicitMember',dimension='us-gaap:SubsegmentsAxis');third.text='fixture:ProductMember'
    (folder/'instance.xml').write_bytes(etree.tostring(changed))
    assert {r['segment_raw'] for r in gev_rows() if r['axis']=='business'}=={'DataCenterMember'}
    (folder/'instance.xml').write_bytes(etree.tostring(document).replace(b'http://www.gevernova.com/20260630',b'http://example.invalid/impostor'))
    assert not [r for r in gev_rows() if r['axis']=='business']
