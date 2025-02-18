import os
import json
import logging

logger = logging.getLogger('TitleFilter')

class TitleFilter:
    def __init__(self, config_file: str = 'config/keywords_filter.json'):
        self.config_file = config_file
        self.remove_chars = []
        self.remove_words = []
        self.replace_rules = []
        self.load_config()
    
    def load_config(self):
        """加载过滤配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.remove_chars = config.get('remove_chars', [])
                    self.remove_words = config.get('remove_words', [])
                    self.replace_rules = config.get('replace_rules', [])
                logger.info(f"加载标题过滤配置：{len(self.remove_chars)} 个字符，{len(self.remove_words)} 个关键词，{len(self.replace_rules)} 个替换规则")
            else:
                logger.warning(f"过滤配置文件不存在：{self.config_file}")
        except Exception as e:
            logger.error(f"加载过滤配置失败：{str(e)}")
    
    def filter_title(self, title: str) -> str:
        """过滤标题"""
        if not title:
            return title
            
        # 移除特殊字符
        filtered_title = title
        for char in self.remove_chars:
            filtered_title = filtered_title.replace(char, '')
        
        # 移除关键词
        for word in self.remove_words:
            filtered_title = filtered_title.replace(word, '')
        
        # 应用替换规则
        for rule in self.replace_rules:
            filtered_title = filtered_title.replace(rule['from'], rule['to'])
        
        # 清理多余的空格
        filtered_title = ' '.join(filtered_title.split())
        
        return filtered_title
    
    def save_config(self):
        """保存过滤配置"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'remove_chars': self.remove_chars,
                    'remove_words': self.remove_words,
                    'replace_rules': self.replace_rules
                }, f, ensure_ascii=False, indent=4)
            logger.info("过滤配置已保存")
        except Exception as e:
            logger.error(f"保存过滤配置失败：{str(e)}")
    
    def add_char(self, char: str):
        """添加需要移除的字符"""
        if char not in self.remove_chars:
            self.remove_chars.append(char)
            self.save_config()
    
    def add_word(self, word: str):
        """添加需要移除的关键词"""
        if word not in self.remove_words:
            self.remove_words.append(word)
            self.save_config()
    
    def remove_char(self, char: str):
        """删除过滤字符"""
        if char in self.remove_chars:
            self.remove_chars.remove(char)
            self.save_config()
    
    def remove_word(self, word: str):
        """删除过滤关键词"""
        if word in self.remove_words:
            self.remove_words.remove(word)
            self.save_config()
    
    def get_config(self) -> dict:
        """获取当前配置"""
        return {
            'remove_chars': self.remove_chars,
            'remove_words': self.remove_words,
            'replace_rules': self.replace_rules
        }
    
    def add_replace_rule(self, from_text: str, to_text: str):
        """添加替换规则"""
        rule = {'from': from_text, 'to': to_text}
        if rule not in self.replace_rules:
            self.replace_rules.append(rule)
            self.save_config()
    
    def remove_replace_rule(self, from_text: str, to_text: str):
        """删除替换规则"""
        rule = {'from': from_text, 'to': to_text}
        if rule in self.replace_rules:
            self.replace_rules.remove(rule)
            self.save_config()