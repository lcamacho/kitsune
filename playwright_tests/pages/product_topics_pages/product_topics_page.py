from playwright.sync_api import Page
from playwright_tests.core.basepage import BasePage


class ProductTopicPage(BasePage):
    # Product topic page content locators.
    __page_title = "//h1[@class='topic-title sumo-page-heading']"
    __page_subheading = "//div[@class='sumo-article-header--text']/p"

    # Product topic page navbar locators.
    __navbar_links = "//a[@data-event-action='topic sidebar']"
    __selected_nav_link = "//a[contains(@class,'selected')]"

    # Product topic page learn more locators.
    __learn_more_button = "//section[@id='get-involved-button']//a"

    # Product topic page still need help locators.
    __still_need_help_subheading = "//div[contains(@class, 'aaq-widget')]/p"
    __aaq_button = "//a[@data-event-label='aaq widget']"

    def __init__(self, page: Page):
        super().__init__(page)

    # Page content actions.
    def _get_page_title(self) -> str:
        return super()._get_text_of_element(self.__page_title)

    # Navbar actions.
    def _get_selected_navbar_option(self) -> str:
        return super()._get_text_of_element(self.__selected_nav_link)

    def _click_on_a_navbar_option(self, option_name: str):
        xpath = f'//a[@data-event-action="topic sidebar" and contains(text(), "{option_name}")]'
        super()._click(xpath)

    def _get_navbar_links_text(self) -> list[str]:
        return super()._get_text_of_elements(self.__navbar_links)

    def _get_navbar_option_link(self, option_name: str) -> str:
        xpath = f'//a[@data-event-action="topic sidebar" and contains(text(), "{option_name}")]'
        return super()._get_element_attribute_value(xpath, "href")

    # AAQ section actions.
    def _get_aaq_subheading_text(self) -> str:
        return super()._get_text_of_element(self.__still_need_help_subheading)

    def _click_on_aaq_button(self):
        super()._click(self.__aaq_button)

    # Learn more section actions.
    def _click_on_learn_more_button(self):
        super()._click(self.__learn_more_button)
