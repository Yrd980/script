
"""
Script to remove all comments from multiple programming languages.
Uses design patterns: Strategy, Factory, Template Method, and Command patterns.
Supports: Java, JavaScript, TypeScript, Vue, Python, Go, Rust, C++, C
"""

import os
import re
import glob
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from enum import Enum

class CommentType(Enum):
    """Enumeration of comment types."""
    SINGLE_LINE = "single_line"
    MULTI_LINE = "multi_line"
    JAVADOC = "javadoc"
    HTML = "html"
    POD = "pod"
    HASKELL = "haskell"
    LUA = "lua"

class CommentStrategy(ABC):
    """Abstract base class for comment removal strategies."""
    
    @abstractmethod
    def remove_comments(self, content: str) -> str:
        """Remove comments from the given content."""
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Get list of file extensions this strategy supports."""
        pass

class SingleLineCommentStrategy(CommentStrategy):
    """Strategy for removing single-line comments."""
    
    def __init__(self, comment_marker: str):
        self.comment_marker = comment_marker
    
    def remove_comments(self, content: str) -> str:
        """Remove single-line comments using the specified marker."""
        lines = content.split('\n')
        result_lines = []
        
        for line in lines:
            if not line.strip():
                result_lines.append(line)
                continue
            
            comment_pos = self._find_comment_position(line)
            if comment_pos >= 0:
                result_lines.append(line[:comment_pos].rstrip())
            else:
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    def _find_comment_position(self, line: str) -> int:
        """Find the position of comment marker that's not in a string."""
        in_string = False
        string_char = None
        
        for i, char in enumerate(line):
            if char in ['"', "'"]:
                if not in_string:
                    in_string = True
                    string_char = char
                elif string_char == char:
                    in_string = False
                    string_char = None
            elif not in_string:
                if self.comment_marker == '//' and char == '/' and i + 1 < len(line) and line[i + 1] == '/':
                    return i
                elif self.comment_marker == '#' and char == '#':
                    return i
                elif self.comment_marker == '--' and char == '-' and i + 1 < len(line) and line[i + 1] == '-':
                    return i
        
        return -1
    
    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return []

class MultiLineCommentStrategy(CommentStrategy):
    """Strategy for removing multi-line comments."""
    
    def __init__(self, start_marker: str, end_marker: str):
        self.start_marker = start_marker
        self.end_marker = end_marker
        self.pattern = re.escape(start_marker) + r'.*?' + re.escape(end_marker)
    
    def remove_comments(self, content: str) -> str:
        """Remove multi-line comments using regex pattern."""
        return re.sub(self.pattern, '', content, flags=re.DOTALL)
    
    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return []

class CompositeCommentStrategy(CommentStrategy):
    """Composite strategy that combines multiple comment removal strategies."""
    
    def __init__(self, strategies: List[CommentStrategy], extensions: List[str]):
        self.strategies = strategies
        self.extensions = extensions
    
    def remove_comments(self, content: str) -> str:
        """Apply all strategies in sequence."""
        result = content
        for strategy in self.strategies:
            result = strategy.remove_comments(result)
        return result
    
    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return self.extensions

class LanguageCommentRemover:
    """Template class for language-specific comment removal."""
    
    def __init__(self, strategy: CommentStrategy):
        self.strategy = strategy
    
    def remove_comments(self, content: str) -> str:
        """Template method for comment removal."""
        return self.strategy.remove_comments(content)

class CommentRemoverFactory:
    """Factory for creating comment removal strategies."""
    
    _strategies: Dict[str, CommentStrategy] = {}
    
    @classmethod
    def register_strategy(cls, language: str, strategy: CommentStrategy):
        """Register a strategy for a language."""
        cls._strategies[language] = strategy
    
    @classmethod
    def get_strategy(cls, file_extension: str) -> CommentStrategy:
        """Get the appropriate strategy for a file extension."""
        return cls._strategies.get(file_extension.lower())
    
    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """Get all supported file extensions."""
        return list(cls._strategies.keys())

class FileProcessor:
    """Command pattern implementation for file processing."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.original_content = None
        self.processed_content = None
    
    def execute(self) -> bool:
        """Execute the file processing command."""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.original_content = f.read()
            
            strategy = CommentRemoverFactory.get_strategy(self._get_file_extension())
            if not strategy:
                return False
            
            remover = LanguageCommentRemover(strategy)
            self.processed_content = remover.remove_comments(self.original_content)
            
            if self.processed_content != self.original_content:
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    f.write(self.processed_content)
                return True
            
            return False
            
        except Exception as e:
            print(f"Error processing {self.file_path}: {e}")
            return False
    
    def _get_file_extension(self) -> str:
        """Get file extension."""
        return os.path.splitext(self.file_path)[1]

class CommentRemovalOrchestrator:
    """Orchestrator class that coordinates the comment removal process."""
    
    def __init__(self):
        self._setup_strategies()
    
    def _setup_strategies(self):
        """Setup all comment removal strategies."""

        java_strategy = CompositeCommentStrategy([
            MultiLineCommentStrategy('/**', '*/'),
            MultiLineCommentStrategy('/*', '*/'),
            SingleLineCommentStrategy('//')
        ], ['.java'])
        CommentRemoverFactory.register_strategy('.java', java_strategy)
        

        js_strategy = CompositeCommentStrategy([
            MultiLineCommentStrategy('/*', '*/'),
            SingleLineCommentStrategy('//')
        ], ['.js', '.jsx', '.ts', '.tsx'])
        CommentRemoverFactory.register_strategy('.js', js_strategy)
        CommentRemoverFactory.register_strategy('.jsx', js_strategy)
        CommentRemoverFactory.register_strategy('.ts', js_strategy)
        CommentRemoverFactory.register_strategy('.tsx', js_strategy)
        

        python_strategy = SingleLineCommentStrategy('#')
        CommentRemoverFactory.register_strategy('.py', python_strategy)
        

        go_strategy = CompositeCommentStrategy([
            MultiLineCommentStrategy('/*', '*/'),
            SingleLineCommentStrategy('//')
        ], ['.go'])
        CommentRemoverFactory.register_strategy('.go', go_strategy)
        

        rust_strategy = CompositeCommentStrategy([
            MultiLineCommentStrategy('/*', '*/'),
            SingleLineCommentStrategy('//')
        ], ['.rs'])
        CommentRemoverFactory.register_strategy('.rs', rust_strategy)
        

        cpp_strategy = CompositeCommentStrategy([
            MultiLineCommentStrategy('/*', '*/'),
            SingleLineCommentStrategy('//')
        ], ['.c', '.h', '.cpp', '.cc', '.cxx', '.hpp', '.hxx'])
        CommentRemoverFactory.register_strategy('.c', cpp_strategy)
        CommentRemoverFactory.register_strategy('.h', cpp_strategy)
        CommentRemoverFactory.register_strategy('.cpp', cpp_strategy)
        CommentRemoverFactory.register_strategy('.cc', cpp_strategy)
        CommentRemoverFactory.register_strategy('.cxx', cpp_strategy)
        CommentRemoverFactory.register_strategy('.hpp', cpp_strategy)
        CommentRemoverFactory.register_strategy('.hxx', cpp_strategy)
        

        csharp_strategy = CompositeCommentStrategy([
            MultiLineCommentStrategy('/*', '*/'),
            SingleLineCommentStrategy('//')
        ], ['.cs'])
        CommentRemoverFactory.register_strategy('.cs', csharp_strategy)
        

        dart_strategy = CompositeCommentStrategy([
            MultiLineCommentStrategy('/*', '*/'),
            SingleLineCommentStrategy('//')
        ], ['.dart'])
        CommentRemoverFactory.register_strategy('.dart', dart_strategy)
        

        php_strategy = CompositeCommentStrategy([
            MultiLineCommentStrategy('/*', '*/'),
            SingleLineCommentStrategy('//'),
            SingleLineCommentStrategy('#')
        ], ['.php'])
        CommentRemoverFactory.register_strategy('.php', php_strategy)
        

        ruby_strategy = SingleLineCommentStrategy('#')
        CommentRemoverFactory.register_strategy('.rb', ruby_strategy)
        

        swift_strategy = CompositeCommentStrategy([
            MultiLineCommentStrategy('/*', '*/'),
            SingleLineCommentStrategy('//')
        ], ['.swift'])
        CommentRemoverFactory.register_strategy('.swift', swift_strategy)
        

        kotlin_strategy = CompositeCommentStrategy([
            MultiLineCommentStrategy('/*', '*/'),
            SingleLineCommentStrategy('//')
        ], ['.kt'])
        CommentRemoverFactory.register_strategy('.kt', kotlin_strategy)
        

        scala_strategy = CompositeCommentStrategy([
            MultiLineCommentStrategy('/*', '*/'),
            SingleLineCommentStrategy('//')
        ], ['.scala'])
        CommentRemoverFactory.register_strategy('.scala', scala_strategy)
        

        haskell_strategy = CompositeCommentStrategy([
            MultiLineCommentStrategy('{-', '-}'),
            SingleLineCommentStrategy('--')
        ], ['.hs'])
        CommentRemoverFactory.register_strategy('.hs', haskell_strategy)
        

        lua_strategy = CompositeCommentStrategy([
            MultiLineCommentStrategy('--[[', ']]'),
            SingleLineCommentStrategy('--')
        ], ['.lua'])
        CommentRemoverFactory.register_strategy('.lua', lua_strategy)
        

        perl_strategy = CompositeCommentStrategy([
            MultiLineCommentStrategy('=pod', '=cut'),
            SingleLineCommentStrategy('#')
        ], ['.pl'])
        CommentRemoverFactory.register_strategy('.pl', perl_strategy)
        

        shell_strategy = SingleLineCommentStrategy('#')
        CommentRemoverFactory.register_strategy('.sh', shell_strategy)
        CommentRemoverFactory.register_strategy('.bash', shell_strategy)
        CommentRemoverFactory.register_strategy('.zsh', shell_strategy)
        CommentRemoverFactory.register_strategy('.fish', shell_strategy)
        

        sql_strategy = CompositeCommentStrategy([
            MultiLineCommentStrategy('/*', '*/'),
            SingleLineCommentStrategy('--')
        ], ['.sql'])
        CommentRemoverFactory.register_strategy('.sql', sql_strategy)
        

        vue_strategy = self._create_vue_strategy()
        CommentRemoverFactory.register_strategy('.vue', vue_strategy)
    
    def _create_vue_strategy(self) -> CommentStrategy:
        """Create a special strategy for Vue files."""
        class VueCommentStrategy(CommentStrategy):
            def remove_comments(self, content: str) -> str:

                content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
                

                def process_script_content(match):
                    script_content = match.group(1)
                    js_strategy = CompositeCommentStrategy([
                        MultiLineCommentStrategy('/*', '*/'),
                        SingleLineCommentStrategy('//')
                    ], [])
                    return f'<script{js_strategy.remove_comments(script_content)}</script>'
                
                content = re.sub(r'<script(.*?)</script>', process_script_content, content, flags=re.DOTALL)
                

                return SingleLineCommentStrategy('//').remove_comments(content)
            
            def get_supported_extensions(self) -> List[str]:
                return ['.vue']
        
        return VueCommentStrategy()
    
    def process_files(self, patterns: List[str]) -> Dict[str, int]:
        """Process files using the specified patterns."""
        processed_files = 0
        modified_files = 0
        
        for pattern in patterns:
            for file_path in glob.glob(pattern, recursive=True):
                if os.path.isfile(file_path):
                    processor = FileProcessor(file_path)
                    processed_files += 1
                    if processor.execute():
                        modified_files += 1
                        print(f"Modified: {file_path}")
        
        return {
            'processed': processed_files,
            'modified': modified_files
        }

def main():
    """Main function using the orchestrator pattern."""
    orchestrator = CommentRemovalOrchestrator()
    
    patterns = [
        '**/*.java',
        '**/*.js', '**/*.jsx', '**/*.ts', '**/*.tsx',
        '**/*.vue',
        '**/*.py',
        '**/*.go',
        '**/*.rs',
        '**/*.cpp', '**/*.cc', '**/*.cxx', '**/*.hpp', '**/*.hxx',
        '**/*.c', '**/*.h',
        '**/*.cs',
        '**/*.dart',
        '**/*.php',
        '**/*.rb',
        '**/*.swift',
        '**/*.kt',
        '**/*.scala',
        '**/*.hs',
        '**/*.lua',
        '**/*.pl',
        '**/*.sh', '**/*.bash', '**/*.zsh', '**/*.fish',
        '**/*.sql'
    ]
    
    results = orchestrator.process_files(patterns)
    
    print(f"\nSummary:")
    print(f"Processed files: {results['processed']}")
    print(f"Modified files: {results['modified']}")

if __name__ == "__main__":
    main()
