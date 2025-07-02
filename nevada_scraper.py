#!/usr/bin/env python3
"""
Nevada Entity Search Scraper
Scrapes business entity information from Nevada Secretary of State website
"""

from seleniumbase import SB
import time
import requests
import json
import os
import sys

# Configuration
API_KEY = os.getenv('SOLVECAPTCHA_API_KEY', "e8241ace650146ad502519d5ef2bf819")
SOLVE_URL = "https://api.solvecaptcha.com/in.php"
RESULT_URL = "https://api.solvecaptcha.com/res.php"
NEVADA_URL = "https://esos.nv.gov/EntitySearch/OnlineEntitySearch"

def solve_captcha(sitekey, pageurl):
    """Solve hCaptcha using external API"""
    try:
        # Submit captcha
        payload = {
            'key': API_KEY,
            'method': 'hcaptcha',
            'sitekey': sitekey,
            'pageurl': pageurl,
            'json': '1'
        }
        
        print("Submitting captcha to API...")
        response = requests.post(SOLVE_URL, data=payload, timeout=30)
        response_data = response.json()
        
        if response_data.get('status') != 1:
            raise Exception(f"Failed to submit captcha: {response_data}")
            
        request_id = response_data['request']
        print(f"Captcha submitted successfully. Request ID: {request_id}")
        
        # Wait for solution
        max_attempts = 120  # 2 minutes maximum wait time
        attempts = 0
        
        while attempts < max_attempts:
            time.sleep(1)
            result_payload = {
                'key': API_KEY,
                'action': 'get',
                'id': request_id,
                'json': '1'
            }
            
            result = requests.get(RESULT_URL, params=result_payload, timeout=10)
            result_data = result.json()
            
            if result_data.get('status') == 1:
                print("Captcha solved successfully!")
                return {
                    'token': result_data['request'],
                    'useragent': result_data.get('useragent'),
                    'respKey': result_data.get('respKey')
                }
            
            attempts += 1
            print(f"Waiting for solution... Attempt {attempts}/{max_attempts}")
            
        raise Exception("Timeout waiting for captcha solution")
        
    except Exception as e:
        print(f"Error solving captcha: {str(e)}")
        raise

def parse_business_information(html_content):
    """Parse business information from Nevada entity search HTML and return structured data"""
    try:
        from bs4 import BeautifulSoup
        import json
        import re
        
        print("Parsing business information from HTML...")
        soup = BeautifulSoup(html_content, 'html.parser')
        
        business_data = {
            "entity_information": {},
            "registered_agent": {},
            "officers": [],
            "metadata": {
                "source": "Nevada Secretary of State",
                "scraped_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "success": True
            }
        }
        
        # Parse Entity Information
        panel_bodies = soup.find_all('div', class_='panel-body')
        
        for panel in panel_bodies:
            # Look for entity information fields
            rows = panel.find_all('div', class_='row form-group')
            
            for row in rows:
                labels = row.find_all('label', class_='control-label')
                
                for label in labels:
                    label_text = label.get_text(strip=True).replace(':', '')
                    
                    # Find the corresponding value
                    parent_div = label.parent
                    next_div = parent_div.find_next_sibling('div')
                    
                    if next_div:
                        value = next_div.get_text(strip=True)
                        
                        # Map labels to JSON fields
                        if 'Entity Name' in label_text:
                            business_data['entity_information']['entity_name'] = value
                        elif 'Entity Number' in label_text:
                            business_data['entity_information']['entity_number'] = value
                        elif 'Entity Type' in label_text:
                            business_data['entity_information']['entity_type'] = value
                        elif 'Entity Status' in label_text:
                            business_data['entity_information']['entity_status'] = value
                        elif 'Formation Date' in label_text:
                            business_data['entity_information']['formation_date'] = value
                        elif 'NV Business ID' in label_text and 'entity_information' in business_data:
                            # Only set if not already set (to avoid overwriting with agent's ID)
                            if 'nv_business_id' not in business_data['entity_information']:
                                business_data['entity_information']['nv_business_id'] = value
                        elif 'Termination Date' in label_text:
                            business_data['entity_information']['termination_date'] = value if value else None
                        elif 'Annual Report Due Date' in label_text:
                            business_data['entity_information']['annual_report_due_date'] = value
                        elif 'Compliance Hold' in label_text:
                            business_data['entity_information']['compliance_hold'] = value if value else None
                        
                        # Registered Agent Information
                        elif 'Name of Individual or Legal Entity' in label_text:
                            business_data['registered_agent']['name'] = value
                        elif 'Status' in label_text and 'registered_agent' in business_data and 'name' in business_data['registered_agent']:
                            business_data['registered_agent']['status'] = value
                        elif 'CRA Agent Entity Type' in label_text:
                            business_data['registered_agent']['cra_agent_entity_type'] = value if value else None
                        elif 'Registered Agent Type' in label_text:
                            business_data['registered_agent']['registered_agent_type'] = value
                        elif 'NV Business ID' in label_text and 'registered_agent' in business_data and 'name' in business_data['registered_agent']:
                            business_data['registered_agent']['nv_business_id'] = value
                        elif 'Office or Position' in label_text:
                            business_data['registered_agent']['office_or_position'] = value if value else None
                        elif 'Jurisdiction' in label_text:
                            business_data['registered_agent']['jurisdiction'] = value if value else None
                        elif 'Street Address' in label_text:
                            business_data['registered_agent']['street_address'] = value
                        elif 'Mailing Address' in label_text:
                            business_data['registered_agent']['mailing_address'] = value if value else None
        
        # Parse Officer Information (Table)
        officer_table = soup.find('table', {'id': 'grid_principalList'})
        if officer_table:
            tbody = officer_table.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')
                
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 5:
                        officer = {
                            'title': cells[0].get_text(strip=True),
                            'name': cells[1].get_text(strip=True),
                            'address': cells[2].get_text(strip=True),
                            'last_updated': cells[3].get_text(strip=True),
                            'status': cells[4].get_text(strip=True)
                        }
                        business_data['officers'].append(officer)
        
        return business_data
        
    except ImportError:
        print("BeautifulSoup4 not installed. Please install it: pip install beautifulsoup4")
        return None
    except Exception as e:
        print(f"Error parsing business information: {str(e)}")
        return None

def scrape_nevada_entity(file_number):
    """Main scraping function for a single Nevada entity"""
    print(f"🚀 Starting Nevada entity search for: {file_number}")
    
    try:
        with SB(uc=True, locale="en", headless=True, xvfb=True) as sb:
            sb.activate_cdp_mode(NEVADA_URL, tzone="America/Panama")
            sb.sleep(3)

            # First try to find search input on main page (no captcha needed)
            try:
                print("Checking for search input on main page...")
                sb.wait_for_element_present('input[id="BusinessSearch_Index_txtEntityNumber"]', timeout=5)
                print("Search input found on main page - no captcha needed!")

            except:
                # Search input not found, proceed with captcha solving
                print("Search input not found on main page")
                print("Looking for captcha iframe...")

                try:
                    # Wait for and switch to the iframe (only exists if captcha is present)
                    print("Waiting for iframe to be present...")
                    sb.wait_for_element_present('iframe#main-iframe')
                    sb.switch_to_frame('iframe#main-iframe')
                    print("Switched to iframe")

                    # Extract sitekey from within the iframe
                    sitekey = sb.get_attribute('div[class="h-captcha"]', 'data-sitekey')
                    print(f"Found sitekey: {sitekey}")

                    if sitekey:
                        try:
                            # Solve captcha
                            captcha_data = solve_captcha(sitekey, NEVADA_URL)

                            # Set useragent if provided
                            if captcha_data.get('useragent'):
                                sb.execute_script(
                                    f'navigator.userAgent = "{captcha_data["useragent"]}";'
                                )

                            # Set both response fields
                            js_script = f'''
                                document.querySelector("[name=h-captcha-response]").innerHTML = "{captcha_data['token']}";
                                document.querySelector("[name=g-recaptcha-response]").innerHTML = "{captcha_data['token']}";
                                if (typeof onCaptchaFinished === 'function') {{
                                    onCaptchaFinished("{captcha_data['token']}");
                                }}
                            '''
                            sb.execute_script(js_script)
                            sb.switch_to_default_content()
                            print("Captcha response set successfully")

                        except Exception as captcha_error:
                            print(f"Failed to handle captcha: {captcha_error}")
                    else:
                        print("No captcha sitekey found in iframe")

                except Exception as iframe_error:
                    print(f"No iframe found or iframe error: {iframe_error}")
                    print("Proceeding without captcha solving")

            # Perform the search
            print(f"Performing search for file number: {file_number}")
            sb.sleep(3)
            sb.click('input[id="BusinessSearch_Index_txtEntityNumber"]')
            sb.type('input[id="BusinessSearch_Index_txtEntityNumber"]', file_number)
            sb.click('input[id="btnSearch"]')
            sb.click('a[onclick*="GetBusinessSearchResultById"]')
            sb.wait_for_element_present('div[class="panel-body"]', timeout=10)
            
            # Get the HTML content
            html = sb.get_page_source()
            
            # Parse the business information from the HTML
            business_data = parse_business_information(html)
            
            if business_data:
                print("✅ Business data extracted successfully")
                return business_data
            else:
                raise Exception("Failed to parse business information")
                
    except Exception as e:
        print(f"❌ Error during scraping: {str(e)}")
        return {
            "entity_information": {},
            "registered_agent": {},
            "officers": [],
            "metadata": {
                "source": "Nevada Secretary of State",
                "scraped_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "success": False,
                "error": str(e)
            }
        }

def main():
    """Main execution function"""
    try:
        # Get file number from environment variable
        file_number = os.getenv('FILE_NUMBER', 'E10281132020-8')
        request_id = os.getenv('REQUEST_ID', f'nevada-{int(time.time())}')
        
        print(f"🚀 Starting Nevada business scraper (Request ID: {request_id})")
        print(f"File number to process: {file_number}")
        
        # Check if API key is available
        if not API_KEY:
            print("❌ ERROR: SOLVECAPTCHA_API_KEY environment variable not set")
            sys.exit(1)
        
        # Scrape the entity
        result = scrape_nevada_entity(file_number)
        
        if result:
            # Add metadata
            result['metadata']['file_number_searched'] = file_number
            result['metadata']['request_id'] = request_id
            
            # Create filename
            output_file = f'scraped_data_{file_number}_{request_id}.json'
            
            # Save as JSON
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\n💾 Scraped data saved to {output_file}")
            
            # Output JSON data to console for GitHub Actions
            print("\n=== SCRAPED_DATA_JSON_START ===")
            print(json.dumps(result, indent=2))
            print("=== SCRAPED_DATA_JSON_END ===")
            
            # Print summary
            entity_name = result.get('entity_information', {}).get('entity_name', 'N/A')
            entity_status = result.get('entity_information', {}).get('entity_status', 'N/A')
            officer_count = len(result.get('officers', []))
            success = result.get('metadata', {}).get('success', False)
            
            print(f"\n🎉 NEVADA SCRAPING COMPLETE!")
            print(f"📊 File number processed: {file_number}")
            print(f"🏢 Entity name: {entity_name}")
            print(f"📋 Entity status: {entity_status}")
            print(f"👥 Number of officers: {officer_count}")
            print(f"✅ Success: {success}")
            print(f"📄 Output format: JSON")
            
            if not success:
                error = result.get('metadata', {}).get('error', 'Unknown error')
                print(f"❌ Error: {error}")
                sys.exit(1)
        else:
            print("\n❌ No data was scraped")
            sys.exit(1)
        
    except Exception as e:
        print(f"\n💥 Error in scraping process: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
